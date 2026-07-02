#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier

fail() {
  echo 0 > /logs/verifier/reward.txt
  exit 0
}

pass() {
  echo 1 > /logs/verifier/reward.txt
  exit 0
}

cd /testbed || fail

cp /opt/baseline/test/router.test.ts test/router.test.ts || fail
cp /opt/baseline/test/find-all.test.ts test/find-all.test.ts || fail

if command -v python3 >/dev/null 2>&1; then
  python3 /tests/test_outputs.py --describe >/tmp/alibaba_test_outputs_description.txt 2>/dev/null || true
fi

cat > /tmp/alibaba_test_patch.diff <<'__ALIBABA_TEST_PATCH__'
diff --git a/test/find-all.test.ts b/test/find-all.test.ts
index ac7e389..34cacee 100644
--- a/test/find-all.test.ts
+++ b/test/find-all.test.ts
@@ -62,6 +62,18 @@ describe("find-matchAll: basic", () => {
   });
 });
 
+describe("matcher: repeated regex modifiers", () => {
+  const router = createRouter(["/digits/:id(\\d+)+", "/digits/:slug+"]);
+
+  it("keeps inline constraints when collecting all repeated-parameter matches", () => {
+    expect(_findAllRoutes(router, "GET", "/digits/123/456")).toEqual([
+      "/digits/:id(\\d+)+",
+      "/digits/:slug+",
+    ]);
+    expect(_findAllRoutes(router, "GET", "/digits/abc/def")).toEqual(["/digits/:slug+"]);
+  });
+});
+
 describe("matcher: complex", () => {
   const router = createRouter([
     "/",
diff --git a/test/router.test.ts b/test/router.test.ts
index 2ac693e..3416c91 100644
--- a/test/router.test.ts
+++ b/test/router.test.ts
@@ -594,6 +594,33 @@ describe("Router lookup", function () {
         data: { path: "/files/:path*" },
       },
     });
+
+    // :name(regex)+ — one or more constrained segments
+    testRouter(["/digits/:id(\\d+)+"], undefined, {
+      "/digits/123": {
+        data: { path: "/digits/:id(\\d+)+" },
+        params: { id: "123" },
+      },
+      "/digits/123/456": {
+        data: { path: "/digits/:id(\\d+)+" },
+        params: { id: "123/456" },
+      },
+      "/digits/abc": undefined,
+      "/digits/123/abc": undefined,
+    });
+
+    // :name(regex)* — zero or more constrained segments
+    testRouter(["/maybe-digits/:id(\\d+)*"], undefined, {
+      "/maybe-digits": {
+        data: { path: "/maybe-digits/:id(\\d+)*" },
+      },
+      "/maybe-digits/123/456": {
+        data: { path: "/maybe-digits/:id(\\d+)*" },
+        params: { id: "123/456" },
+      },
+      "/maybe-digits/abc": undefined,
+      "/maybe-digits/123/abc": undefined,
+    });
   });
 
   describe("non-capturing groups", function () {
__ALIBABA_TEST_PATCH__

git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff || patch -p1 --fuzz=5 < /tmp/alibaba_test_patch.diff || fail

pnpm vitest run test/router.test.ts test/find-all.test.ts --reporter=dot
cmd_status=$?

if [ "$cmd_status" -eq 0 ]; then
  pass
else
  fail
fi
