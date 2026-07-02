#!/bin/bash
set -euo pipefail

cd /testbed

cat > /tmp/alibaba_gold_patch.diff <<'__ALIBABA_GOLD_PATCH__'
diff --git a/src/compiler.ts b/src/compiler.ts
index 993b82d..d10225a 100644
--- a/src/compiler.ts
+++ b/src/compiler.ts
@@ -126,7 +126,7 @@ function compileMethodMatch(
       if (key !== "") code += `if(m==="${key}")${matchers.length > 1 ? "{" : ""}`;
       const _matchers = matchers
         .map((m) => compileFinalMatch(ctx, m, currentIdx, params))
-        .sort((a, b) => b.weight - a.weight);
+        .sort((a, b) => (ctx.opts?.matchAll ? a.weight - b.weight : b.weight - a.weight));
       for (const matcher of _matchers) {
         code += matcher.code;
       }
@@ -147,19 +147,19 @@ function compileFinalMatch(
   const conditions: string[] = [];
 
   // Add param properties
-  const { paramsMap, paramsRegexp } = data;
+  const { paramsMap } = data;
   if (paramsMap && paramsMap.length > 0) {
     // Check for optional end parameters
     const required = !paramsMap[paramsMap.length - 1][2] && currentIdx !== -1;
     if (required) {
       conditions.push(`l>${currentIdx}`);
     }
-    for (let i = 0; i < paramsRegexp.length; i++) {
-      const regexp = paramsRegexp[i];
-      if (!regexp) {
+    for (let i = 0; i < paramsMap.length; i++) {
+      const param = paramsMap[i][1];
+      if (typeof param === "string") {
         continue;
       }
-      conditions.push(`${regexp.toString()}.test(s[${i + 1}])`);
+      conditions.push(`${param.toString()}.test(${params[i]})`);
     }
 
     // Create the param object based on previous parameters
diff --git a/src/operations/_utils.ts b/src/operations/_utils.ts
index 4005688..fb6ed64 100644
--- a/src/operations/_utils.ts
+++ b/src/operations/_utils.ts
@@ -27,8 +27,8 @@ export function expandModifiers(segments: string[]): string[] | undefined {
     if (m[2] === "?") {
       return ["/" + pre.concat(m[1]).concat(suf).join("/"), "/" + pre.concat(suf).join("/")];
     }
-    const name = m[1].match(/:([\w-]+)/)?.[1] || "_";
-    const wc = "/" + [...pre, `**:${name}`, ...suf].join("/");
+    const [, name = "_", pattern] = m[1].match(/:([\w-]+)(?:\(([^)]*)\))?$/) || [];
+    const wc = "/" + [...pre, `**:${name}${pattern ? `(${pattern})` : ""}`, ...suf].join("/");
     const without = "/" + [...pre, ...suf].join("/");
     return m[2] === "+" ? [wc] : [wc, without];
   }
diff --git a/src/operations/add.ts b/src/operations/add.ts
index 06d0461..16c877a 100644
--- a/src/operations/add.ts
+++ b/src/operations/add.ts
@@ -59,7 +59,16 @@ export function addRoute<T>(
         node.wildcard = { key: "**" };
       }
       node = node.wildcard;
-      paramsMap.push([-(i + 1), segment.split(":")[1] || "_", segment.length === 2 /* no id */]);
+      const [, name = "_", pattern] =
+        segment.match(/^\*\*(?::([\w-]+)(?:\((.*)\))?)?$/) || [];
+      if (pattern) {
+        const repeated = `${pattern}(?:/${pattern})*`;
+        const regexp = new RegExp(`^(?<${name}>${repeated})$`);
+        paramsRegexp[i] = regexp;
+        paramsMap.push([-(i + 1), regexp, false]);
+      } else {
+        paramsMap.push([-(i + 1), name, segment.length === 2 /* no id */]);
+      }
       break;
     }
 
diff --git a/src/operations/find-all.ts b/src/operations/find-all.ts
index 2def8c8..e18e20a 100644
--- a/src/operations/find-all.ts
+++ b/src/operations/find-all.ts
@@ -44,7 +44,13 @@ function _findAll<T>(
   if (node.wildcard && node.wildcard.methods) {
     const match = node.wildcard.methods[method] || node.wildcard.methods[""];
     if (match) {
-      matches.push(...match);
+      const rest = segments.slice(index).join("/");
+      matches.push(
+        ...match.filter((m) => {
+          const param = m.paramsMap?.[m.paramsMap.length - 1]?.[1];
+          return !(param instanceof RegExp) || param.test(rest);
+        }),
+      );
     }
   }
 
diff --git a/src/operations/find.ts b/src/operations/find.ts
index 84778c1..f753bcb 100644
--- a/src/operations/find.ts
+++ b/src/operations/find.ts
@@ -110,7 +110,15 @@ function _lookupTree<T>(
 
   // 3. Wildcard
   if (node.wildcard && node.wildcard.methods) {
-    return node.wildcard.methods[method] || node.wildcard.methods[""];
+    const match = node.wildcard.methods[method] || node.wildcard.methods[""];
+    if (match) {
+      const rest = segments.slice(index).join("/");
+      const exactMatch = match.find((m) => {
+        const param = m.paramsMap?.[m.paramsMap.length - 1]?.[1];
+        return !(param instanceof RegExp) || param.test(rest);
+      });
+      return exactMatch ? [exactMatch] : undefined;
+    }
   }
 
   // No match
__ALIBABA_GOLD_PATCH__

git apply --whitespace=nowarn /tmp/alibaba_gold_patch.diff || patch -p1 --fuzz=5 < /tmp/alibaba_gold_patch.diff
echo "Applied Alibaba sample reference solution."
