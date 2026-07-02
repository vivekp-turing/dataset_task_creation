#!/usr/bin/env python3
"""Long-horizon Harbor upgrades batch 2: aiogram, grpc-java, devoxxgenie, avalonia."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_build_harbor_tasks import ALL_TASKS, apply_text_patch, build_one, noop_bug  # noqa: E402
from long_horizon_tasks import write_new_file  # noqa: E402


def fix_aiogram(wt: Path) -> None:
    """Payload length validation after encoding + shared deeplink payload helpers."""
    write_new_file(
        wt,
        "aiogram/utils/deeplink_payload.py",
        '''"""Shared deep-link payload normalization and Telegram length guards."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from aiogram.utils.payload import encode_payload

if TYPE_CHECKING:
    from collections.abc import Callable

BAD_PATTERN = re.compile(r"[^a-zA-Z0-9-_]")
DEFAULT_MAX_LENGTH = 64


def normalize_payload_text(payload: object) -> str:
    """Coerce payload values to str for deep-link assembly."""
    if isinstance(payload, str):
        return payload
    return str(payload)


def materialize_deeplink_payload(
    payload: object,
    *,
    encode: bool = False,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str:
    """Return the payload string that will appear in the deep link query."""
    text = normalize_payload_text(payload)
    if encode or encoder is not None:
        return encode_payload(text, encoder=encoder)
    return text


def assert_deeplink_payload(
    payload: object,
    *,
    max_length: int = DEFAULT_MAX_LENGTH,
    encode: bool = False,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str:
    """Validate charset and Telegram length on the final deep-link payload."""
    final = materialize_deeplink_payload(payload, encode=encode, encoder=encoder)

    if re.search(BAD_PATTERN, final):
        msg = (
            "Wrong payload! Only A-Z, a-z, 0-9, _ and - are allowed. "
            "Pass `encode=True` or encode payload manually."
        )
        raise ValueError(msg)

    if len(final) > max_length:
        msg = f"Payload must be up to {max_length} characters long."
        raise ValueError(msg)

    return final
''',
    )
    apply_text_patch(
        wt,
        "aiogram/utils/payload.py",
        "def decode_payload(",
        '''def materialize_deeplink_payload(
    payload: str,
    *,
    encode: bool = False,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str:
    """Return payload text after optional encoding (without charset validation)."""
    if not isinstance(payload, str):
        payload = str(payload)
    if encode or encoder is not None:
        return encode_payload(payload, encoder=encoder)
    return payload


def decode_payload(''',
    )
    apply_text_patch(
        wt,
        "aiogram/utils/deep_linking.py",
        "from aiogram.utils.link import create_telegram_link\nfrom aiogram.utils.payload import decode_payload, encode_payload",
        "from aiogram.utils.deeplink_payload import assert_deeplink_payload\nfrom aiogram.utils.link import create_telegram_link\nfrom aiogram.utils.payload import decode_payload, encode_payload",
    )
    apply_text_patch(
        wt,
        "aiogram/utils/deep_linking.py",
        "BAD_PATTERN = re.compile(r\"[^a-zA-Z0-9-_]\")\nDEEPLINK_PAYLOAD_LENGTH = 64\n",
        "DEEPLINK_PAYLOAD_LENGTH = 64\n",
    )
    apply_text_patch(
        wt,
        "aiogram/utils/deep_linking.py",
        """    if not isinstance(payload, str):
        payload = str(payload)

    if len(payload) > DEEPLINK_PAYLOAD_LENGTH:
        msg = f"Payload must be up to {DEEPLINK_PAYLOAD_LENGTH} characters long."
        raise ValueError(msg)

    if encode or encoder:
        payload = encode_payload(payload, encoder=encoder)

    if re.search(BAD_PATTERN, payload):
        msg = (
            "Wrong payload! Only A-Z, a-z, 0-9, _ and - are allowed. "
            "Pass `encode=True` or encode payload manually."
        )
        raise ValueError(msg)

    # length guard removed

    if not app_name:""",
        """    payload = assert_deeplink_payload(
        payload,
        max_length=DEEPLINK_PAYLOAD_LENGTH,
        encode=encode,
        encoder=encoder,
    )

    if not app_name:""",
    )
    apply_text_patch(
        wt,
        "aiogram/utils/link.py",
        "def create_telegram_link(*path: str, **kwargs: Any) -> str:\n    return _format_url(\"https://t.me\", *path, **kwargs)",
        '''def create_telegram_link(*path: str, **kwargs: Any) -> str:
    """Build https://t.me links, omitting empty query values."""
    filtered = {key: value for key, value in kwargs.items() if value is not None and value != ""}
    return _format_url("https://t.me", *path, **filtered)''',
    )


def bug_aiogram(c: Path) -> None:
    """Pre-encoding length check lets encoded payloads exceed Telegram limits."""
    apply_text_patch(
        c,
        "aiogram/utils/deep_linking.py",
        """    if not isinstance(payload, str):
        payload = str(payload)

    if encode or encoder:""",
        """    if not isinstance(payload, str):
        payload = str(payload)

    if len(payload) > DEEPLINK_PAYLOAD_LENGTH:
        msg = f"Payload must be up to {DEEPLINK_PAYLOAD_LENGTH} characters long."
        raise ValueError(msg)

    if encode or encoder:""",
    )


def fix_grpc_java(wt: Path) -> None:
    """Extract gRPC content-type parsing with + and ; suffix support."""
    write_new_file(
        wt,
        "core/src/main/java/io/grpc/internal/GrpcContentTypeParser.java",
        '''/*
 * Copyright 2024 The gRPC Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package io.grpc.internal;

import java.util.Locale;

/** Parses and validates gRPC HTTP/2 content-type headers. */
final class GrpcContentTypeParser {

  private GrpcContentTypeParser() {}

  static boolean isGrpcContentType(String contentType, String baseType) {
    if (contentType == null) {
      return false;
    }

    String normalized = normalizeContentType(contentType);
    if (baseType.length() > normalized.length()) {
      return false;
    }

    if (!normalized.startsWith(baseType)) {
      return false;
    }

    if (normalized.length() == baseType.length()) {
      return true;
    }

    char suffixStart = normalized.charAt(baseType.length());
    return suffixStart == '+' || suffixStart == ';';
  }

  static String normalizeContentType(String contentType) {
    return contentType.trim().toLowerCase(Locale.US);
  }

  static boolean hasValidGrpcSuffix(String contentType, String baseType) {
    if (contentType == null || baseType == null) {
      return false;
    }
    String normalized = normalizeContentType(contentType);
    if (!normalized.startsWith(baseType) || normalized.length() <= baseType.length()) {
      return false;
    }
    char suffixStart = normalized.charAt(baseType.length());
    return suffixStart == '+' || suffixStart == ';';
  }
}
''',
    )
    apply_text_patch(
        wt,
        "core/src/main/java/io/grpc/internal/GrpcUtil.java",
        """  public static boolean isGrpcContentType(String contentType) {
    if (contentType == null) {
      return false;
    }

    if (CONTENT_TYPE_GRPC.length() > contentType.length()) {
      return false;
    }

    contentType = contentType.toLowerCase(Locale.US);
    if (!contentType.startsWith(CONTENT_TYPE_GRPC)) {
      // Not a gRPC content-type.
      return false;
    }

    if (contentType.length() == CONTENT_TYPE_GRPC.length()) {
      // The strings match exactly.
      return true;
    }

    // The contentType matches, but is longer than the expected string.
    // We need to support variations on the content-type (e.g. +proto, +json) as defined by the
    // gRPC wire spec.
    char nextChar = contentType.charAt(CONTENT_TYPE_GRPC.length());
    return nextChar == '+';
  }""",
        """  public static boolean isGrpcContentType(String contentType) {
    return GrpcContentTypeParser.isGrpcContentType(contentType, CONTENT_TYPE_GRPC);
  }""",
    )
    apply_text_patch(
        wt,
        "core/src/main/java/io/grpc/internal/Http2ClientStreamTransportState.java",
        '      return status.augmentDescription("invalid content-type: " + contentType);',
        '      return status.augmentDescription(\n'
        '          "invalid content-type: "\n'
        '              + GrpcContentTypeParser.normalizeContentType(contentType));',
    )


def bug_grpc_java(c: Path) -> None:
    noop_bug(c)

def fix_devoxxgenie(wt: Path) -> None:
    """Shared path normalization in FileUtil + UI callers."""
    apply_text_patch(
        wt,
        "src/main/java/com/devoxx/genie/util/FileUtil.java",
        """public class FileUtil {

    /**
     * Get the file type of the file which represents the programming language (if any) of the file.""",
        """public class FileUtil {

    private static @NotNull String normalizeSeparators(@NotNull String path) {
        return path.replace('\\\\', '/');
    }

    private static @NotNull String stripLeadingSeparators(@NotNull String path) {
        int start = 0;
        while (start < path.length() && (path.charAt(start) == '/' || path.charAt(start) == '\\\\')) {
            start++;
        }
        return path.substring(start);
    }

    static boolean isPathUnderBase(@NotNull String basePath, @NotNull String filePath) {
        String base = normalizeSeparators(basePath);
        String file = normalizeSeparators(filePath);
        if (!base.endsWith("/")) {
            base = base + "/";
        }
        return file.equals(base.substring(0, base.length() - 1)) || file.startsWith(base);
    }

    public static @NotNull String getParentDirectoryForDisplay(@NotNull String relativePath, @NotNull String fileName) {
        if (relativePath.isEmpty() || relativePath.equals(fileName)) {
            return "";
        }
        if (!relativePath.endsWith(fileName)) {
            return relativePath;
        }
        return relativePath.substring(0, relativePath.length() - fileName.length());
    }

    public static @NotNull String getDisplayRelativePath(@NotNull Project project, @NotNull VirtualFile file) {
        return getRelativePath(project, file);
    }

    /**
     * Get the file type of the file which represents the programming language (if any) of the file.""",
    )
    apply_text_patch(
        wt,
        "src/main/java/com/devoxx/genie/util/FileUtil.java",
        """        if (projectBasePath != null && filePath.startsWith(projectBasePath)) {
            String relativePath = filePath.substring(projectBasePath.length());
            // leading slash strip removed
            return relativePath;
        }

        return filePath;""",
        """        if (projectBasePath != null && isPathUnderBase(projectBasePath, filePath)) {
            String base = normalizeSeparators(projectBasePath);
            String normalizedFile = normalizeSeparators(filePath);
            if (normalizedFile.equals(base) || normalizedFile.equals(base + "/")) {
                return "";
            }
            if (!base.endsWith("/")) {
                base = base + "/";
            }
            String relativePath = normalizedFile.substring(base.length());
            return stripLeadingSeparators(relativePath);
        }

        return filePath;""",
    )
    apply_text_patch(
        wt,
        "src/main/java/com/devoxx/genie/ui/panel/FileListCellRenderer.java",
        """            String fullPath = FileUtil.getRelativePath(project, file);
            if (!fullPath.equals(file.getName())) {
                String path = fullPath.substring(0, fullPath.lastIndexOf(file.getName()));
                pathLabel.setText(path);""",
        """            String fullPath = FileUtil.getDisplayRelativePath(project, file);
            String path = FileUtil.getParentDirectoryForDisplay(fullPath, file.getName());
            if (!path.isEmpty()) {
                pathLabel.setText(path);""",
    )
    apply_text_patch(
        wt,
        "src/main/java/com/devoxx/genie/ui/component/FileEntryComponent.java",
        """        String fullPath = FileUtil.getRelativePath(project, file);

        if (!fullPath.equals(file.getName())) {
            pathLabel.setText(fullPath);""",
        """        String relativePath = FileUtil.getDisplayRelativePath(project, file);

        if (!relativePath.isEmpty() && !relativePath.equals(file.getName())) {
            pathLabel.setText(relativePath);""",
    )


def fix_avalonia(wt: Path) -> None:
    """AllSidesEqual on Thickness + border/layout/size guards."""
    apply_text_patch(
        wt,
        "src/Avalonia.Base/Thickness.cs",
        """        /// <summary>
        /// Gets a value indicating whether all sides are equal.
        /// </summary>
        public bool IsUniform => Left.Equals(Right) && Top.Equals(Bottom);""",
        """        /// <summary>
        /// Returns true when all four sides of the thickness are equal.
        /// </summary>
        public static bool AllSidesEqual(Thickness thickness)
        {
            return thickness.Left.Equals(thickness.Top)
                && thickness.Top.Equals(thickness.Right)
                && thickness.Right.Equals(thickness.Bottom);
        }

        public static bool CanUseUniformBorderFastPath(Thickness borderThickness)
        {
            return AllSidesEqual(borderThickness);
        }

        public static bool TryGetUniformValue(Thickness thickness, out double value)
        {
            if (!AllSidesEqual(thickness))
            {
                value = default;
                return false;
            }

            value = thickness.Left;
            return true;
        }

        /// <summary>
        /// Gets a value indicating whether all sides are equal.
        /// </summary>
        public bool IsUniform => AllSidesEqual(this);""",
    )
    apply_text_patch(
        wt,
        "src/Avalonia.Controls/Utils/BorderRenderHelper.cs",
        """            if (borderThickness.IsUniform &&
                (cornerRadius.IsUniform || _backendSupportsIndividualCorners == true) &&
                backgroundSizing == BackgroundSizing.CenterBorder)""",
        """            if (Thickness.CanUseUniformBorderFastPath(borderThickness) &&
                (cornerRadius.IsUniform || _backendSupportsIndividualCorners == true) &&
                backgroundSizing == BackgroundSizing.CenterBorder)""",
    )
    apply_text_patch(
        wt,
        "src/Avalonia.Base/Layout/LayoutHelper.cs",
        """        public static Thickness RoundLayoutThickness(Thickness thickness, double dpiScale)
        {
            // If DPI == 1, don't use DPI-aware rounding.
            return dpiScale == 1.0 ?
                new Thickness(
                    Math.Round(thickness.Left),
                    Math.Round(thickness.Top),
                    Math.Round(thickness.Right),
                    Math.Round(thickness.Bottom)) :
                new Thickness(
                    Math.Round(thickness.Left * dpiScale) / dpiScale,
                    Math.Round(thickness.Top * dpiScale) / dpiScale,
                    Math.Round(thickness.Right * dpiScale) / dpiScale,
                    Math.Round(thickness.Bottom * dpiScale) / dpiScale);
        }""",
        """        public static Thickness RoundLayoutThickness(Thickness thickness, double dpiScale)
        {
            if (Thickness.TryGetUniformValue(thickness, out var uniform))
            {
                var rounded = dpiScale == 1.0
                    ? Math.Round(uniform)
                    : Math.Round(uniform * dpiScale) / dpiScale;
                return new Thickness(rounded);
            }

            // If DPI == 1, don't use DPI-aware rounding.
            return dpiScale == 1.0 ?
                new Thickness(
                    Math.Round(thickness.Left),
                    Math.Round(thickness.Top),
                    Math.Round(thickness.Right),
                    Math.Round(thickness.Bottom)) :
                new Thickness(
                    Math.Round(thickness.Left * dpiScale) / dpiScale,
                    Math.Round(thickness.Top * dpiScale) / dpiScale,
                    Math.Round(thickness.Right * dpiScale) / dpiScale,
                    Math.Round(thickness.Bottom * dpiScale) / dpiScale);
        }""",
    )
    apply_text_patch(
        wt,
        "src/Avalonia.Base/Size.cs",
        """        public Size Deflate(Thickness thickness)
        {
            var width = _width - thickness.Left - thickness.Right;
            if (width < 0)
                width = 0;

            var height = _height - thickness.Top - thickness.Bottom;
            if (height < 0)
                height = 0;

            return new Size(width, height);
        }""",
        """        public Size Deflate(Thickness thickness)
        {
            if (Thickness.TryGetUniformValue(thickness, out var uniform))
            {
                var total = uniform + uniform;
                var uniformWidth = _width - total;
                if (uniformWidth < 0)
                    uniformWidth = 0;
                var uniformHeight = _height - total;
                if (uniformHeight < 0)
                    uniformHeight = 0;
                return new Size(uniformWidth, uniformHeight);
            }

            var width = _width - thickness.Left - thickness.Right;
            if (width < 0)
                width = 0;

            var height = _height - thickness.Top - thickness.Bottom;
            if (height < 0)
                height = 0;

            return new Size(width, height);
        }""",
    )


LH_PATCHES: dict[str, dict] = {
    "aiogram": {
        "apply_bug": bug_aiogram,
        "apply_fix": fix_aiogram,
        "instruction": (
            "Telegram deep links must enforce the 64-character payload limit on the final value "
            "that appears in the URL, including after optional base64url encoding or custom "
            "encoders. Charset validation must run on that same post-encoding string. Shared "
            "payload preparation and length guards should live in one place and be reused by "
            "create_deep_link rather than checking raw length before encoding."
        ),
        "one_sentence": (
            "Fix deep-link payload validation: enforce Telegram length after encoding with "
            "shared helpers across deeplink_payload, payload, deep_linking, and link assembly."
        ),
        "why_worth_using": (
            "Models add a raw-length check or a single-file guard; encoded payloads, startapp "
            "paths, and charset rules expose partial fixes."
        ),
        "rubric_correctness": (
            "- Length enforced on post-encoding payload string.\n"
            "- Encoded overlong payloads rejected; exactly 64 accepted.\n"
            "- Shared deeplink_payload helper used by create_deep_link.\n"
            "- test_deep_linking pass2pass stays green."
        ),
        "test_files": {
            "tests/test_utils/conftest.py": """
                import pytest
                from tests.mocked_bot import MockedBot

                @pytest.fixture
                def bot():
                    return MockedBot()
            """,
            "tests/test_deep_linking_lh_seeded.py": """
                import pytest

                from aiogram.utils.deep_linking import create_deep_link
                from aiogram.utils.payload import encode_payload

                def test_rejects_overlong_raw_payload():
                    with pytest.raises(ValueError, match="64"):
                        create_deep_link("bot", "start", "x" * 65)

                def test_accepts_exactly_64_chars():
                    payload = "a" * 64
                    link = create_deep_link("bot", "start", payload)
                    assert payload in link

                def test_accepts_valid_short_payload():
                    link = create_deep_link("bot", "start", "hello")
                    assert "hello" in link

                def test_rejects_overlong_after_encoding():
                    raw = "?" * 49
                    with pytest.raises(ValueError, match="64"):
                        create_deep_link("bot", "start", raw, encode=True)

                def test_accepts_encoded_payload_under_limit():
                    raw = "?" * 20
                    encoded = encode_payload(raw)
                    assert len(encoded) <= 64
                    link = create_deep_link("bot", "start", raw, encode=True)
                    assert encoded in link

                def test_startgroup_respects_length():
                    with pytest.raises(ValueError, match="64"):
                        create_deep_link("bot", "startgroup", "y" * 65)

                def test_startapp_with_app_name_respects_length():
                    with pytest.raises(ValueError, match="64"):
                        create_deep_link("bot", "startapp", "z" * 65, app_name="mini")

                def test_non_string_payload_coerced_and_validated():
                    with pytest.raises(ValueError, match="64"):
                        create_deep_link("bot", "start", 10**64)

                def test_materialize_matches_create_deep_link_encoding():
                    from aiogram.utils.payload import materialize_deeplink_payload

                    raw = "payload-with-dashes_and_underscores"
                    assert materialize_deeplink_payload(raw, encode=True) == encode_payload(raw)

                def test_custom_encoder_expansion_rejected():
                    def expand(_: bytes) -> bytes:
                        return b"x" * 80

                    with pytest.raises(ValueError, match="64"):
                        create_deep_link("bot", "start", "ok", encode=True, encoder=expand)
            """,
        },
        "dockerfile": """FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN pip install --no-cache-dir -e . pytest pytest-asyncio pycryptodomex
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\n"
            "rm -f tests/test_deep_linking_lh_seeded.py tests/test_deep_link_length_seeded.py\n"
            "rm -f tests/test_utils/conftest.py\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "pytest tests/test_deep_linking_lh_seeded.py tests/test_utils/test_deep_linking.py "
            "-q --confcutdir=tests/test_utils&&pass||fail\n"
        ),
    },
    "grpc-java": {
        "apply_bug": bug_grpc_java,
        "apply_fix": fix_grpc_java,
        "instruction": (
            "gRPC content-type validation must accept wire-compatible suffixes introduced with "
            "either '+' or ';' after the application/grpc base type, trim surrounding whitespace "
            "before comparison, and centralize parsing in a shared helper used by GrpcUtil and "
            "HTTP/2 stream validation paths."
        ),
        "one_sentence": (
            "Fix gRPC content-type parsing: shared parser with + and ; suffixes, trim, and "
            "Http2ClientStreamTransportState integration."
        ),
        "why_worth_using": (
            "Single-character patches pass semicolon cases but miss whitespace, shared parsing, "
            "and downstream error normalization."
        ),
        "rubric_correctness": (
            "- application/grpc;params and +proto variants accepted.\n"
            "- Whitespace-padded types accepted; non-grpc rejected.\n"
            "- GrpcContentTypeParser shared by GrpcUtil.\n"
            "- GrpcUtilTest pass2pass stays green."
        ),
        "test_files": {
            "core/src/test/java/io/grpc/internal/GrpcUtilLongHorizonSeededTest.java": """
                package io.grpc.internal;

                import static org.junit.Assert.assertFalse;
                import static org.junit.Assert.assertTrue;
                import org.junit.Test;

                public class GrpcUtilLongHorizonSeededTest {
                  @Test
                  public void semicolonSuffixValid() {
                    assertTrue(GrpcUtil.isGrpcContentType(GrpcUtil.CONTENT_TYPE_GRPC + ";proto"));
                  }

                  @Test
                  public void plusSuffixValid() {
                    assertTrue(GrpcUtil.isGrpcContentType(GrpcUtil.CONTENT_TYPE_GRPC + "+proto"));
                  }

                  @Test
                  public void exactMatchValid() {
                    assertTrue(GrpcUtil.isGrpcContentType(GrpcUtil.CONTENT_TYPE_GRPC));
                  }

                  @Test
                  public void semicolonWithParamsValid() {
                    assertTrue(
                        GrpcUtil.isGrpcContentType(
                            GrpcUtil.CONTENT_TYPE_GRPC + ";proto=1;encoding=identity"));
                  }

                  @Test
                  public void whitespacePaddedValid() {
                    assertTrue(
                        GrpcUtil.isGrpcContentType("  " + GrpcUtil.CONTENT_TYPE_GRPC + "+json  "));
                  }

                  @Test
                  public void uppercaseBaseValid() {
                    assertTrue(GrpcUtil.isGrpcContentType("APPLICATION/GRPC;proto"));
                  }

                  @Test
                  public void invalidPrefixRejected() {
                    assertFalse(GrpcUtil.isGrpcContentType("application/bad"));
                  }

                  @Test
                  public void invalidSuffixRejected() {
                    assertFalse(GrpcUtil.isGrpcContentType(GrpcUtil.CONTENT_TYPE_GRPC + "proto"));
                  }

                  @Test
                  public void nullRejected() {
                    assertFalse(GrpcUtil.isGrpcContentType(null));
                  }
                }
            """,
        },
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\n"
            "rm -f core/src/test/java/io/grpc/internal/GrpcUtilLongHorizonSeededTest.java\n"
            "rm -f core/src/test/java/io/grpc/internal/GrpcUtilSeededTest.java\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "./gradlew :grpc-core:test "
            "--tests io.grpc.internal.GrpcUtilLongHorizonSeededTest "
            "--tests io.grpc.internal.GrpcUtilTest "
            "-PskipAndroid=true --no-daemon -q&&pass||fail\n"
        ),
    },

    "devoxxgenie": {
        "apply_bug": noop_bug,
        "apply_fix": fix_devoxxgenie,
        "instruction": (
            "Project-relative paths shown in the plugin UI must be normalized: strip leading "
            "separators after removing the base path, normalize Windows-style separators, and "
            "match project roots on path boundaries (not naive prefix checks). Shared helpers "
            "in FileUtil must drive both list-cell parent-path rendering and file-entry labels."
        ),
        "one_sentence": (
            "Normalize project-relative paths in FileUtil and wire UI callers to shared display helpers."
        ),
        "why_worth_using": (
            "Models patch only the slash strip in FileUtil; list renderer substring logic and "
            "base-path boundary checks must stay coordinated across three files."
        ),
        "rubric_correctness": (
            "- FileUtil strips leading separators and normalizes separators.\n"
            "- isPathUnderBase avoids project/project2 prefix collisions.\n"
            "- FileListCellRenderer and FileEntryComponent use display helpers.\n"
            "- Existing FileUtilTest pass2pass stays green."
        ),
        "test_files": {
            "src/test/java/com/devoxx/genie/util/FileUtilLongHorizonSeededTest.java": """
                package com.devoxx.genie.util;
                import com.intellij.openapi.project.Project;
                import com.intellij.openapi.vfs.VirtualFile;
                import org.junit.jupiter.api.Test;
                import org.junit.jupiter.api.extension.ExtendWith;
                import org.mockito.Mock;
                import org.mockito.junit.jupiter.MockitoExtension;
                import static org.assertj.core.api.Assertions.assertThat;
                import static org.mockito.Mockito.when;
                @ExtendWith(MockitoExtension.class)
                class FileUtilLongHorizonSeededTest {
                  @Mock Project project; @Mock VirtualFile file;
                  @Test void noLeadingSlash() {
                    when(project.getBasePath()).thenReturn("/proj");
                    when(file.getPath()).thenReturn("/proj/src/App.java");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("src/App.java");
                  }
                  @Test void nestedPath() {
                    when(project.getBasePath()).thenReturn("/home/user/project");
                    when(file.getPath()).thenReturn("/home/user/project/src/main/java/App.java");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("src/main/java/App.java");
                  }
                  @Test void atProjectRoot_returnsFileName() {
                    when(project.getBasePath()).thenReturn("/proj");
                    when(file.getPath()).thenReturn("/proj/build.gradle");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("build.gradle");
                  }
                  @Test void outsideProject_returnsFullPath() {
                    when(project.getBasePath()).thenReturn("/proj");
                    when(file.getPath()).thenReturn("/tmp/external.txt");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("/tmp/external.txt");
                  }
                  @Test void nullBasePath_returnsFullPath() {
                    when(project.getBasePath()).thenReturn(null);
                    when(file.getPath()).thenReturn("/proj/src/App.java");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("/proj/src/App.java");
                  }
                  @Test void windowsSeparators_normalized() {
                    when(project.getBasePath()).thenReturn("C:/Users/dev/project");
                    when(file.getPath()).thenReturn("C:/Users/dev/project/src/App.java");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("src/App.java");
                  }
                  @Test void similarPrefix_notUnderBase() {
                    when(project.getBasePath()).thenReturn("/home/user/project");
                    when(file.getPath()).thenReturn("/home/user/project2/src/App.java");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("/home/user/project2/src/App.java");
                  }
                  @Test void fileEqualsBase_returnsEmpty() {
                    when(project.getBasePath()).thenReturn("/proj");
                    when(file.getPath()).thenReturn("/proj");
                    assertThat(FileUtil.getRelativePath(project, file)).isEmpty();
                  }
                  @Test void leadingSlash_stripped() {
                    when(project.getBasePath()).thenReturn("/proj");
                    when(file.getPath()).thenReturn("/proj/README.md");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("README.md");
                  }
                  @Test void deepNested_noLeadingSlash() {
                    when(project.getBasePath()).thenReturn("/workspace/app");
                    when(file.getPath()).thenReturn("/workspace/app/modules/core/src/Main.java");
                    assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("modules/core/src/Main.java");
                  }
                }
            """,
        },
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\n"
            "rm -f src/test/java/com/devoxx/genie/util/FileUtilLongHorizonSeededTest.java "
            "src/test/java/com/devoxx/genie/util/FileUtilSeededTest.java\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "./gradlew test --tests com.devoxx.genie.util.FileUtilLongHorizonSeededTest "
            "--tests com.devoxx.genie.util.FileUtilTest --no-daemon -q&&pass||fail\n"
        ),
    },
    "avalonia": {
        "apply_bug": noop_bug,
        "apply_fix": fix_avalonia,
        "instruction": (
            "Thickness uniform detection must return true only when all four sides are equal. "
            "Thickness values with matching horizontal and vertical pairs but differing "
            "right/bottom sides are incorrectly reported as uniform, breaking border fast-path "
            "rendering and layout rounding. AllSidesEqual helpers must be shared by IsUniform, "
            "BorderRenderHelper, RoundLayoutThickness, and Size.Deflate."
        ),
        "one_sentence": (
            "Fix Thickness.IsUniform via AllSidesEqual and wire border/layout/size guards."
        ),
        "why_worth_using": (
            "Models patch only IsUniform; CanUseUniformBorderFastPath, "
            "TryGetUniformValue, RoundLayoutThickness, and Size.Deflate must stay coordinated."
        ),
        "rubric_correctness": (
            "- AllSidesEqual requires four matching sides.\n"
            "- IsUniform delegates to AllSidesEqual.\n"
            "- BorderRenderHelper uses CanUseUniformBorderFastPath.\n"
            "- RoundLayoutThickness and Size.Deflate use TryGetUniformValue.\n"
            "- Existing ThicknessTests pass2pass stay green."
        ),
        "test_files": {
            "tests/Avalonia.Base.UnitTests/ThicknessLongHorizonSeededTests.cs": """
                using Xunit;
                namespace Avalonia.Base.UnitTests {
                  public class ThicknessLongHorizonSeededTests {
                    [Fact] public void Detects_non_uniform_four_side() {
                      Assert.False(new Thickness(1, 2, 1, 2).IsUniform);
                    }
                    [Fact] public void Uniform_all_sides_true() {
                      Assert.True(new Thickness(2, 2, 2, 2).IsUniform);
                    }
                    [Fact] public void Horizontal_vertical_pairs_not_uniform() {
                      Assert.False(new Thickness(1, 1, 2, 2).IsUniform);
                    }
                    [Fact] public void Left_right_match_top_bottom_diff() {
                      Assert.False(new Thickness(3, 3, 3, 4).IsUniform);
                    }
                    [Fact] public void AllSidesEqual_static_helper() {
                      var t = new Thickness(5, 5, 5, 5);
                      Assert.True(Thickness.AllSidesEqual(t));
                      Assert.False(Thickness.AllSidesEqual(new Thickness(1, 2, 3, 4)));
                    }
                    [Fact] public void Uniform_constructor_is_uniform() {
                      Assert.True(new Thickness(4).IsUniform);
                    }
                    [Fact] public void Horizontal_vertical_constructor_not_uniform_when_diff() {
                      Assert.False(new Thickness(2, 3).IsUniform);
                    }
                    [Fact] public void Zero_thickness_is_uniform() {
                      Assert.True(new Thickness(0).IsUniform);
                      Assert.True(Thickness.AllSidesEqual(default(Thickness)));
                    }
                    [Fact] public void Parsed_uniform_thickness() {
                      Assert.True(Thickness.Parse("2.5").IsUniform);
                    }
                    [Fact] public void Parsed_four_side_non_uniform() {
                      Assert.False(Thickness.Parse("1,2,1,2").IsUniform);
                    }
                  }
                }
            """,
        },
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\n"
            "rm -f tests/Avalonia.Base.UnitTests/ThicknessLongHorizonSeededTests.cs "
            "tests/Avalonia.Base.UnitTests/ThicknessIsUniformSeededTests.cs\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "dotnet test tests/Avalonia.Base.UnitTests/Avalonia.Base.UnitTests.csproj -c Release "
            "--filter-class Avalonia.Base.UnitTests.ThicknessLongHorizonSeededTests "
            "--filter-class Avalonia.Base.UnitTests.ThicknessTests "
            "-p:TestingPlatformDotnetTestSupport=false&&pass||fail\n"
        ),
    },

}
def apply_lh_batch2(slug: str) -> None:
    if slug not in LH_PATCHES:
        raise SystemExit(f"no long-horizon batch2 override for {slug}")
    base = ALL_TASKS[slug]
    ALL_TASKS[slug] = {**base, **LH_PATCHES[slug]}
    build_one(slug, ALL_TASKS[slug])


if __name__ == "__main__":
    slugs = sys.argv[1:] if len(sys.argv) > 1 else list(LH_PATCHES.keys())
    for s in slugs:
        print(f"=== long-horizon batch2 build: {s} ===")
        apply_lh_batch2(s)
