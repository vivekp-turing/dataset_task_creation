#!/usr/bin/env python3
"""Upgrade five Harbor tasks to rou3-grade long-horizon scope (~100 LoC, 2–5 files)."""

from __future__ import annotations

import sys
from pathlib import Path

# Reuse bundle builder primitives.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from batch_build_harbor_tasks import ALL_TASKS, apply_text_patch, build_one, noop_bug  # noqa: E402


def write_new_file(wt: Path, rel: str, content: str) -> None:
    p = wt / rel
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def fix_albumentations(wt: Path) -> None:
    """bbox_utils helper + crop functional + transform normalized_input wiring."""
    apply_text_patch(
        wt,
        "albumentations/core/bbox_utils.py",
        "def clip_bboxes(bboxes: np.ndarray, shape: ShapeType) -> np.ndarray:",
        """def clip_and_filter_boxes_in_crop_space(
    bboxes: np.ndarray,
    crop_width: float,
    crop_height: float,
) -> np.ndarray:
    \"\"\"Clip absolute-space boxes to a crop canvas and drop zero-area rows.\"\"\"
    if bboxes.size == 0:
        return bboxes
    clipped = bboxes.copy()
    clipped[:, [0, 2]] = np.clip(clipped[:, [0, 2]], 0, crop_width)
    clipped[:, [1, 3]] = np.clip(clipped[:, [1, 3]], 0, crop_height)
    widths = clipped[:, 2] - clipped[:, 0]
    heights = clipped[:, 3] - clipped[:, 1]
    visible = (widths > 0) & (heights > 0)
    clipped = clipped[visible]
    if clipped.size == 0:
        return np.zeros((0, bboxes.shape[1]), dtype=np.float32)
    return clipped


def clip_bboxes(bboxes: np.ndarray, shape: ShapeType) -> np.ndarray:""",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/crops/functional.py",
        "from albumentations.core.bbox_utils import denormalize_bboxes, normalize_bboxes",
        "from albumentations.core.bbox_utils import (\n    clip_and_filter_boxes_in_crop_space,\n    denormalize_bboxes,\n    normalize_bboxes,\n)",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/crops/functional.py",
        """    x_min, y_min = crop_coords[:2]

    # Subtract crop coordinates
    cropped_bboxes[:, [0, 2]] -= x_min
    cropped_bboxes[:, [1, 3]] -= y_min

    # Calculate crop shape
    crop_height = crop_coords[3] - crop_coords[1]
    crop_width = crop_coords[2] - crop_coords[0]
    crop_shape = (crop_height, crop_width)

    # Return in same format as input
    return normalize_bboxes(cropped_bboxes, crop_shape) if normalized_input else cropped_bboxes""",
        """    x_min, y_min = crop_coords[:2]
    crop_height = crop_coords[3] - crop_coords[1]
    crop_width = crop_coords[2] - crop_coords[0]

    cropped_bboxes[:, [0, 2]] -= x_min
    cropped_bboxes[:, [1, 3]] -= y_min
    cropped_bboxes = clip_and_filter_boxes_in_crop_space(cropped_bboxes, crop_width, crop_height)
    crop_shape = (crop_height, crop_width)
    return normalize_bboxes(cropped_bboxes, crop_shape) if normalized_input else cropped_bboxes""",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/crops/functional.py",
        """    if crop_params is not None:
        crop_x, crop_y = crop_params[:2]
        # Subtract crop values from x and y coordinates
        denormalized_bboxes[:, [0, 2]] -= crop_x
        denormalized_bboxes[:, [1, 3]] -= crop_y

    if pad_params is not None:""",
        """    if crop_params is not None:
        crop_x, crop_y = crop_params[:2]
        crop_w = crop_params[2] - crop_params[0]
        crop_h = crop_params[3] - crop_params[1]
        denormalized_bboxes[:, [0, 2]] -= crop_x
        denormalized_bboxes[:, [1, 3]] -= crop_y
        denormalized_bboxes = clip_and_filter_boxes_in_crop_space(
            denormalized_bboxes, crop_w, crop_h
        )
        if denormalized_bboxes.size == 0:
            return np.zeros((0, bboxes.shape[1]), dtype=np.float32)

    if pad_params is not None:""",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/crops/functional.py",
        """    x1, y1 = crop_coords[:2]

    cropped_keypoints = keypoints.copy()
    cropped_keypoints[:, 0] -= x1  # Adjust x coordinates
    cropped_keypoints[:, 1] -= y1  # Adjust y coordinates

    return cropped_keypoints""",
        """    x1, y1, x2, y2 = crop_coords
    crop_w = x2 - x1
    crop_h = y2 - y1

    cropped_keypoints = keypoints.copy()
    cropped_keypoints[:, 0] -= x1
    cropped_keypoints[:, 1] -= y1
    cropped_keypoints[:, 0] = np.clip(cropped_keypoints[:, 0], 0, crop_w)
    cropped_keypoints[:, 1] = np.clip(cropped_keypoints[:, 1], 0, crop_h)
    inside = (
        (cropped_keypoints[:, 0] >= 0)
        & (cropped_keypoints[:, 0] < crop_w)
        & (cropped_keypoints[:, 1] >= 0)
        & (cropped_keypoints[:, 1] < crop_h)
    )
    return cropped_keypoints[inside]""",
    )
    apply_text_patch(
        wt,
        "albumentations/core/keypoints_utils.py",
        '    "filter_keypoints",',
        '    "filter_keypoints",\n    "filter_keypoints_in_crop_space",',
    )
    apply_text_patch(
        wt,
        "albumentations/core/keypoints_utils.py",
        "def filter_keypoints(\n    keypoints: np.ndarray,\n    shape: ShapeType,\n    remove_invisible: bool,\n) -> np.ndarray:",
        """def filter_keypoints_in_crop_space(
    keypoints: np.ndarray,
    crop_width: float,
    crop_height: float,
) -> np.ndarray:
    \"\"\"Clip keypoints to a crop canvas and drop points outside the open interval.\"\"\"
    if keypoints.size == 0:
        return keypoints
    clipped = keypoints.copy()
    clipped[:, 0] = np.clip(clipped[:, 0], 0, crop_width)
    clipped[:, 1] = np.clip(clipped[:, 1], 0, crop_height)
    inside = (
        (clipped[:, 0] >= 0)
        & (clipped[:, 0] < crop_width)
        & (clipped[:, 1] >= 0)
        & (clipped[:, 1] < crop_height)
    )
    return clipped[inside]


def filter_keypoints(
    keypoints: np.ndarray,
    shape: ShapeType,
    remove_invisible: bool,
) -> np.ndarray:""",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/crops/functional.py",
        "from albumentations.core.bbox_utils import (\n    clip_and_filter_boxes_in_crop_space,\n    denormalize_bboxes,\n    normalize_bboxes,\n)",
        "from albumentations.core.bbox_utils import (\n    clip_and_filter_boxes_in_crop_space,\n    denormalize_bboxes,\n    normalize_bboxes,\n)\nfrom albumentations.core.keypoints_utils import filter_keypoints_in_crop_space",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/crops/functional.py",
        """    x1, y1, x2, y2 = crop_coords
    crop_w = x2 - x1
    crop_h = y2 - y1

    cropped_keypoints = keypoints.copy()
    cropped_keypoints[:, 0] -= x1
    cropped_keypoints[:, 1] -= y1
    cropped_keypoints[:, 0] = np.clip(cropped_keypoints[:, 0], 0, crop_w)
    cropped_keypoints[:, 1] = np.clip(cropped_keypoints[:, 1], 0, crop_h)
    inside = (
        (cropped_keypoints[:, 0] >= 0)
        & (cropped_keypoints[:, 0] < crop_w)
        & (cropped_keypoints[:, 1] >= 0)
        & (cropped_keypoints[:, 1] < crop_h)
    )
    return cropped_keypoints[inside]""",
        """    x1, y1, x2, y2 = crop_coords
    crop_w = x2 - x1
    crop_h = y2 - y1
    shifted = keypoints.copy()
    shifted[:, 0] -= x1
    shifted[:, 1] -= y1
    return filter_keypoints_in_crop_space(shifted, crop_w, crop_h)""",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/crops/transforms.py",
        '        return fcrops.crop_bboxes_by_coords(bboxes, crop_coords, params["shape"][:2])',
        """        normalized = bboxes.size > 0 and bboxes[0, 0] <= 1.0
        return fcrops.crop_bboxes_by_coords(
            bboxes, crop_coords, params["shape"][:2], normalized_input=normalized
        )""",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/crops/transforms.py",
        '        return fcrops.crop_bboxes_by_coords(bboxes, crop_coords, params["shape"])',
        """        normalized = bboxes.size > 0 and bboxes[0, 0] <= 1.0
        return fcrops.crop_bboxes_by_coords(
            bboxes, crop_coords, params["shape"], normalized_input=normalized
        )""",
    )
    apply_text_patch(
        wt,
        "albumentations/augmentations/geometric/rotate.py",
        """        if self.crop_border:
            return fcrops.crop_bboxes_by_coords(
                bboxes_out,
                (x_min, y_min, x_max, y_max),
                image_shape,
            )""",
        """        if self.crop_border:
            normalized = bboxes.size > 0 and bboxes[0, 0] <= 1.0
            return fcrops.crop_bboxes_by_coords(
                bboxes_out,
                (x_min, y_min, x_max, y_max),
                image_shape,
                normalized_input=normalized,
            )""",
    )


def fix_stylelint(wt: Path) -> None:
    write_new_file(
        wt,
        "lib/utils/editInfoOverlap.mjs",
        """/**
 * Determine whether a candidate fix range overlaps any recorded edit-info ranges.
 *
 * @param {[number, number][]} recorded
 * @param {[number, number]} candidate
 * @returns {boolean}
 */
export default function editInfoOverlap(recorded, candidate) {
\tfor (const range of recorded) {
\t\tif (range[1] <= candidate[0]) continue;
\t\tif (candidate[1] <= range[0]) continue;
\t\treturn true;
\t}
\treturn false;
}
""",
    )
    write_new_file(
        wt,
        "lib/utils/recordFixEditInfo.mjs",
        """/** @import { Node as PostcssNode } from 'postcss' */
import addSemicolonForEditInfo from './addSemicolonForEditInfo.mjs';
import editInfoOverlap from './editInfoOverlap.mjs';
import narrowFixRange from './narrowFixRange.mjs';

/**
 * Apply a postcss fix, narrow its edit range, and record it when non-overlapping.
 *
 * @param {{
 *   apply: () => void;
 *   node: PostcssNode;
 *   fixedNodeRange: [number, number];
 *   rangesOfComputedEditInfos: [number, number][];
 *   result: import('../index.mjs').StylelintPostcssResult;
 * }} args
 * @returns {{range: [number, number], text: string} | undefined}
 */
export default function recordFixEditInfo({
\tapply,
\tnode,
\tfixedNodeRange,
\trangesOfComputedEditInfos,
\tresult,
}) {
\tapply();

\tlet fixData = { range: fixedNodeRange, text: node.toString(result.opts?.syntax) };

\tfixData = addSemicolonForEditInfo(node, fixData);
\tfixData = narrowFixRange(node, fixData);

\tif (editInfoOverlap(rangesOfComputedEditInfos, fixData.range)) {
\t\treturn;
\t}

\trangesOfComputedEditInfos.push(fixData.range);
\treturn fixData;
}
""",
    )
    apply_text_patch(
        wt,
        "lib/utils/report.mjs",
        "import narrowFixRange from './narrowFixRange.mjs';",
        "import recordFixEditInfo from './recordFixEditInfo.mjs';",
    )
    apply_text_patch(
        wt,
        "lib/utils/report.mjs",
        "import rangesOverlap from './rangesOverlap.mjs';",
        "",
    )
    apply_text_patch(
        wt,
        "lib/utils/report.mjs",
        "import addSemicolonForEditInfo from './addSemicolonForEditInfo.mjs';",
        "",
    )
    apply_text_patch(
        wt,
        "lib/utils/rangesOverlap.mjs",
        "if (a[1] < b[0]) return false;",
        "if (a[1] <= b[0]) return false;",
    )
    apply_text_patch(
        wt,
        "lib/utils/narrowFixRange.mjs",
        """\t} else if (endOffset < fixData.range[1]) {
\t\t\tendOffset++;
\t\t\treplacementEndOffset = fixData.text.length;
\t\t}""",
        """\t} else if (endOffset < fixData.range[1]) {
\t\t\tendOffset++;
\t\t\treplacementEndOffset++;
\t\t}""",
    )
    apply_text_patch(
        wt,
        "lib/utils/report.mjs",
        """\t// When recording edit info we want to ensure that there is no overlap with any other fix.
\t// We only record the first fix for each node.
\tif (rangesOfComputedEditInfos.some((range) => rangesOverlap(range, fixedNodeRange))) {
\t\treturn;
\t}

\t// Apply the fix
\tapply();

\tlet fixData = { range: fixedNodeRange, text: node.toString(result.opts?.syntax) };

\tfixData = addSemicolonForEditInfo(node, fixData);

\t// Compute the smallest range and text of the fix
\tfixData = narrowFixRange(node, fixData);

\t// Mark the fixed range as mutated
\trangesOfComputedEditInfos.push(fixData.range);

\treturn fixData;""",
        """\treturn recordFixEditInfo({
\t\tapply,
\t\tnode,
\t\tfixedNodeRange,
\t\trangesOfComputedEditInfos,
\t\tresult,
\t});""",
    )


def fix_recharts(wt: Path) -> None:
    apply_text_patch(
        wt,
        "src/util/tooltip/translate.ts",
        """    if (tooltipBoundary < viewBoxBoundary) {
      return Math.max(positive, viewBoxKey);
    }""",
        """    if (tooltipBoundary < viewBoxBoundary) {
      return Math.max(negative, viewBoxKey);
    }""",
    )
    apply_text_patch(
        wt,
        "src/util/tooltip/translate.ts",
        """  if (tooltipBoundary > viewBoxBoundary) {
    return Math.max(positive, viewBoxKey);
  }""",
        """  if (tooltipBoundary > viewBoxBoundary) {
    return Math.max(negative, viewBoxKey);
  }""",
    )
    apply_text_patch(
        wt,
        "src/util/tooltip/translate.ts",
        """  return clsx(CSS_CLASS_PREFIX, {
    [`${CSS_CLASS_PREFIX}-right`]:
      isNumber(translateX) && coordinate && isNumber(coordinate.x) && translateX >= coordinate.x,
    [`${CSS_CLASS_PREFIX}-left`]:
      isNumber(translateX) && coordinate && isNumber(coordinate.x) && translateX < coordinate.x,
    [`${CSS_CLASS_PREFIX}-bottom`]:
      isNumber(translateY) && coordinate && isNumber(coordinate.y) && translateY >= coordinate.y,
    [`${CSS_CLASS_PREFIX}-top`]:
      isNumber(translateY) && coordinate && isNumber(coordinate.y) && translateY < coordinate.y,
  });""",
        """  const anchorX = coordinate?.x;
  const anchorY = coordinate?.y;
  return clsx(CSS_CLASS_PREFIX, {
    [`${CSS_CLASS_PREFIX}-right`]:
      isNumber(translateX) && isNumber(anchorX) && translateX > anchorX,
    [`${CSS_CLASS_PREFIX}-left`]:
      isNumber(translateX) && isNumber(anchorX) && translateX <= anchorX,
    [`${CSS_CLASS_PREFIX}-bottom`]:
      isNumber(translateY) && isNumber(anchorY) && translateY > anchorY,
    [`${CSS_CLASS_PREFIX}-top`]:
      isNumber(translateY) && isNumber(anchorY) && translateY <= anchorY,
  });""",
    )
    apply_text_patch(
        wt,
        "src/component/TooltipBoundingBox.tsx",
        "    viewBox: { ...props.viewBox, width: props.viewBox.width + 40 },",
        "    viewBox: props.viewBox,",
    )
    apply_text_patch(
        wt,
        "src/state/selectors/selectChartOffsetInternal.ts",
        """export const selectAxisViewBox = createSelector(
  selectChartWidth,
  selectChartHeight,
  (width: number, height: number): CartesianViewBoxRequired => ({
    x: 0,
    y: 0,
    width,
    height,
  }),
);""",
        """export const selectTooltipPlotViewBox = createSelector(
  selectChartOffsetInternal,
  (offset: ChartOffsetInternal): CartesianViewBoxRequired => ({
    x: offset.left,
    y: offset.top,
    width: offset.width,
    height: offset.height,
  }),
);

export const selectAxisViewBox = createSelector(
  selectChartWidth,
  selectChartHeight,
  (width: number, height: number): CartesianViewBoxRequired => ({
    x: 0,
    y: 0,
    width,
    height,
  }),
);""",
    )
    apply_text_patch(
        wt,
        "src/context/chartLayoutContext.tsx",
        "import { selectChartOffsetInternal, selectChartViewBox } from '../state/selectors/selectChartOffsetInternal';",
        "import {\n  selectChartOffsetInternal,\n  selectChartViewBox,\n  selectTooltipPlotViewBox,\n} from '../state/selectors/selectChartOffsetInternal';",
    )
    apply_text_patch(
        wt,
        "src/context/chartLayoutContext.tsx",
        """export const useViewBox = (): CartesianViewBoxRequired | undefined => {
  const panorama = useIsPanorama();
  const rootViewBox = useAppSelector(selectChartViewBox);
  const brushDimensions = useAppSelector(selectBrushDimensions);
  const brushPadding = useAppSelector(selectBrushSettings)?.padding;
  if (!panorama || !brushDimensions || !brushPadding) {
    return rootViewBox;
  }
  return {
    width: brushDimensions.width - brushPadding.left - brushPadding.right,
    height: brushDimensions.height - brushPadding.top - brushPadding.bottom,
    x: brushPadding.left,
    y: brushPadding.top,
  };
};""",
        """export const useViewBox = (): CartesianViewBoxRequired | undefined => {
  const panorama = useIsPanorama();
  const rootViewBox = useAppSelector(selectChartViewBox);
  const brushDimensions = useAppSelector(selectBrushDimensions);
  const brushPadding = useAppSelector(selectBrushSettings)?.padding;
  if (!panorama || !brushDimensions || !brushPadding) {
    return rootViewBox;
  }
  return {
    width: brushDimensions.width - brushPadding.left - brushPadding.right,
    height: brushDimensions.height - brushPadding.top - brushPadding.bottom,
    x: brushPadding.left,
    y: brushPadding.top,
  };
};

/** Plot-area view box (chart offset) for tooltip placement. */
export const useTooltipPlotViewBox = (): CartesianViewBoxRequired | undefined => {
  return useAppSelector(selectTooltipPlotViewBox);
};""",
    )
    apply_text_patch(
        wt,
        "src/component/Tooltip.tsx",
        "import { useViewBox } from '../context/chartLayoutContext';",
        "import { useTooltipPlotViewBox } from '../context/chartLayoutContext';",
    )
    apply_text_patch(
        wt,
        "src/component/Tooltip.tsx",
        "  const viewBox = useViewBox();",
        "  const viewBox = useTooltipPlotViewBox();",
    )


def fix_vercel_ai(wt: Path) -> None:
    apply_text_patch(
        wt,
        "packages/provider-utils/src/streaming-tool-call-tracker.ts",
        "    const index = toolCallDelta.index ?? 0;",
        "    const index = toolCallDelta.index ?? this.toolCalls.length;",
    )
    apply_text_patch(
        wt,
        "packages/openai-compatible/src/chat/openai-compatible-chat-language-model.ts",
        """      if (index == null || forwardedToolCallIndices.has(index)) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }""",
        """      if (index == null) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }
      if (forwardedToolCallIndices.has(index)) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }""",
    )
    apply_text_patch(
        wt,
        "packages/groq/src/groq-chat-language-model.ts",
        "    let toolCallTracker: StreamingToolCallTracker;\n\n    let finishReason:",
        """    let toolCallTracker: StreamingToolCallTracker;

    type PendingGroqToolCall = {
      id: string | null;
      type: string | null;
      bufferedArguments: string;
    };
    const pendingToolCalls = new Map<number, PendingGroqToolCall>();
    const forwardedToolCallIndices = new Set<number>();

    const processGroqToolCallDelta = (
      toolCallDelta: {
        index?: number | null;
        id?: string | null;
        type?: string | null;
        function?: { name?: string | null; arguments?: string | null } | null;
      },
    ) => {
      const index = toolCallDelta.index;

      if (index == null) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }

      if (forwardedToolCallIndices.has(index)) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }

      let pending = pendingToolCalls.get(index);
      if (pending == null) {
        pending = {
          id: toolCallDelta.id ?? null,
          type: toolCallDelta.type ?? null,
          bufferedArguments: '',
        };
        pendingToolCalls.set(index, pending);
      } else {
        if (pending.id == null && toolCallDelta.id != null) {
          pending.id = toolCallDelta.id;
        }
        if (pending.type == null && toolCallDelta.type != null) {
          pending.type = toolCallDelta.type;
        }
      }

      const argumentsDelta = toolCallDelta.function?.arguments;
      if (argumentsDelta != null) {
        pending.bufferedArguments += argumentsDelta;
      }

      const name = toolCallDelta.function?.name;
      if (name != null) {
        toolCallTracker.processDelta({
          index,
          id: pending.id,
          type: pending.type ?? 'function',
          function: { name, arguments: pending.bufferedArguments },
        });
        pendingToolCalls.delete(index);
        forwardedToolCallIndices.add(index);
      }
    };

    let finishReason:""",
    )
    apply_text_patch(
        wt,
        "packages/groq/src/groq-chat-language-model.ts",
        """              for (const toolCallDelta of delta.tool_calls) {
                toolCallTracker.processDelta(toolCallDelta);
              }""",
        """              for (const toolCallDelta of delta.tool_calls) {
                processGroqToolCallDelta(toolCallDelta);
              }""",
    )
    apply_text_patch(
        wt,
        "packages/groq/src/groq-chat-language-model.ts",
        """            toolCallTracker.flush();

            controller.enqueue({
              type: 'finish',
              finishReason,
              usage: convertGroqUsage(usage),
              ...(providerMetadata != null ? { providerMetadata } : {}),
            });""",
        """            for (const [index, pending] of pendingToolCalls) {
              toolCallTracker.processDelta({
                index,
                id: pending.id,
                type: pending.type ?? 'function',
                function: { arguments: pending.bufferedArguments },
              });
            }
            pendingToolCalls.clear();

            toolCallTracker.flush();

            controller.enqueue({
              type: 'finish',
              finishReason,
              usage: convertGroqUsage(usage),
              ...(providerMetadata != null ? { providerMetadata } : {}),
            });""",
    )


def bug_vercel_ai(c: Path) -> None:
    apply_text_patch(
        c,
        "packages/provider-utils/src/streaming-tool-call-tracker.ts",
        "    const index = toolCallDelta.index ?? this.toolCalls.length;",
        "    const index = toolCallDelta.index ?? 0;",
    )
    apply_text_patch(
        c,
        "packages/openai-compatible/src/chat/openai-compatible-chat-language-model.ts",
        """      if (index == null) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }
      if (forwardedToolCallIndices.has(index)) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }""",
        """      if (index == null || forwardedToolCallIndices.has(index)) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }""",
    )
    apply_text_patch(
        c,
        "packages/groq/src/groq-chat-language-model.ts",
        """    type PendingGroqToolCall = {
      id: string | null;
      type: string | null;
      bufferedArguments: string;
    };
    const pendingToolCalls = new Map<number, PendingGroqToolCall>();
    const forwardedToolCallIndices = new Set<number>();

    const processGroqToolCallDelta = (
      toolCallDelta: {
        index?: number | null;
        id?: string | null;
        type?: string | null;
        function?: { name?: string | null; arguments?: string | null } | null;
      },
    ) => {
      const index = toolCallDelta.index;

      if (index == null) {
        const syntheticIndex =
          forwardedToolCallIndices.size + pendingToolCalls.size;
        toolCallTracker.processDelta({ ...toolCallDelta, index: syntheticIndex });
        return;
      }

      if (forwardedToolCallIndices.has(index)) {
        toolCallTracker.processDelta(toolCallDelta);
        return;
      }

      let pending = pendingToolCalls.get(index);
      if (pending == null) {
        pending = {
          id: toolCallDelta.id ?? null,
          type: toolCallDelta.type ?? null,
          bufferedArguments: '',
        };
        pendingToolCalls.set(index, pending);
      } else {
        if (pending.id == null && toolCallDelta.id != null) {
          pending.id = toolCallDelta.id;
        }
        if (pending.type == null && toolCallDelta.type != null) {
          pending.type = toolCallDelta.type;
        }
      }

      const argumentsDelta = toolCallDelta.function?.arguments;
      if (argumentsDelta != null) {
        pending.bufferedArguments += argumentsDelta;
      }

      const name = toolCallDelta.function?.name;
      if (name != null) {
        toolCallTracker.processDelta({
          index,
          id: pending.id,
          type: pending.type ?? 'function',
          function: { name, arguments: pending.bufferedArguments },
        });
        pendingToolCalls.delete(index);
        forwardedToolCallIndices.add(index);
      }
    };

    let finishReason:""",
        "    let toolCallTracker: StreamingToolCallTracker;\n\n    let finishReason:",
    )
    apply_text_patch(
        c,
        "packages/groq/src/groq-chat-language-model.ts",
        """              for (const toolCallDelta of delta.tool_calls) {
                processGroqToolCallDelta(toolCallDelta);
              }""",
        """              for (const toolCallDelta of delta.tool_calls) {
                toolCallTracker.processDelta(toolCallDelta);
              }""",
    )
    apply_text_patch(
        c,
        "packages/groq/src/groq-chat-language-model.ts",
        """            for (const [index, pending] of pendingToolCalls) {
              toolCallTracker.processDelta({
                index,
                id: pending.id,
                type: pending.type ?? 'function',
                function: { arguments: pending.bufferedArguments },
              });
            }
            pendingToolCalls.clear();

            toolCallTracker.flush();

            controller.enqueue({
              type: 'finish',
              finishReason,
              usage: convertGroqUsage(usage),
              ...(providerMetadata != null ? { providerMetadata } : {}),
            });""",
        """            toolCallTracker.flush();

            controller.enqueue({
              type: 'finish',
              finishReason,
              usage: convertGroqUsage(usage),
              ...(providerMetadata != null ? { providerMetadata } : {}),
            });""",
    )


def fix_darts(wt: Path) -> None:
    write_new_file(
        wt,
        "darts/utils/step_alignment.py",
        """\"\"\"Shared helpers for integer/time step alignment across Darts subsystems.\"\"\"

from __future__ import annotations

import pandas as pd

from darts.utils.utils import n_steps_between


def steps_from_end_to(
    end: pd.Timestamp | int,
    start: pd.Timestamp | int,
    freq: pd.DateOffset | int | str,
) -> int:
    \"\"\"Signed step distance from `start` toward `end`.\"\"\"
    return n_steps_between(end=end, start=start, freq=freq)


def train_length_with_covariate_shift(train_length: int, start_shifted: int) -> int:
    \"\"\"Adjust train length when historical forecasts start after covariate trimming.\"\"\"
    return train_length + max(0, start_shifted)


def missing_target_steps_after_forecast(
    forecast_end: pd.Timestamp | int,
    target_end: pd.Timestamp | int,
    freq: pd.DateOffset | int | str,
) -> int:
    \"\"\"How many target steps are missing after the last historical forecast.\"\"\"
    return n_steps_between(end=target_end, start=forecast_end, freq=freq)


def intersect_shift_start(
    self_start: pd.Timestamp | int,
    other_start: pd.Timestamp | int,
    freq: pd.DateOffset | int | str,
) -> int:
    \"\"\"Start offset when slicing intersecting series that share bounds.\"\"\"
    return steps_from_end_to(end=self_start, start=other_start, freq=freq)
""",
    )
    apply_text_patch(
        wt,
        "darts/utils/utils.py",
        "        n_steps = diff // freq if diff != 0 else 1\n",
        "        n_steps = diff // freq\n",
    )
    apply_text_patch(
        wt,
        "darts/utils/__init__.py",
        """from darts.utils.utils import (
    _build_tqdm_iterator,
    _parallel_apply,
    _with_sanity_checks,
    n_steps_between,
)""",
        """from darts.utils.step_alignment import (
    intersect_shift_start,
    missing_target_steps_after_forecast,
    steps_from_end_to,
    train_length_with_covariate_shift,
)
from darts.utils.utils import (
    _build_tqdm_iterator,
    _parallel_apply,
    _with_sanity_checks,
    n_steps_between,
)""",
    )
    apply_text_patch(
        wt,
        "darts/utils/__init__.py",
        '__all__ = [\n    "_build_tqdm_iterator",',
        '__all__ = [\n    "intersect_shift_start",\n    "missing_target_steps_after_forecast",\n    "steps_from_end_to",\n    "train_length_with_covariate_shift",\n    "_build_tqdm_iterator",',
    )
    apply_text_patch(
        wt,
        "darts/utils/data/utils.py",
        "from darts.utils.utils import n_steps_between",
        "from darts.utils.step_alignment import steps_from_end_to",
    )
    apply_text_patch(
        wt,
        "darts/utils/data/utils.py",
        """    return idx + n_steps_between(
        start=ts_target.end_time(), end=ts_covariate.end_time(), freq=freq
    )""",
        """    return idx + steps_from_end_to(
        end=ts_covariate.end_time(), start=ts_target.end_time(), freq=freq
    )""",
    )
    apply_text_patch(
        wt,
        "darts/utils/historical_forecasts/utils.py",
        "        train_length_adjusted = train_length + start_shifted + 1\n",
        "        train_length_adjusted = train_length_with_covariate_shift(train_length, start_shifted)\n",
    )
    apply_text_patch(
        wt,
        "darts/utils/historical_forecasts/utils.py",
        "from darts.utils.utils import n_steps_between",
        "from darts.utils.step_alignment import (\n    missing_target_steps_after_forecast,\n    train_length_with_covariate_shift,\n)\nfrom darts.utils.utils import n_steps_between",
    )
    apply_text_patch(
        wt,
        "darts/timeseries.py",
        """        shift_start = n_steps_between(
            other.start_time(), self.start_time(), freq=self.freq
        )
        shift_end = len(other) - (len(self) - shift_start)""",
        """        shift_start = intersect_shift_start(
            self_start=self.start_time(),
            other_start=other.start_time(),
            freq=self.freq,
        )
        shift_end = len(other) - (len(self) - shift_start)""",
    )
    apply_text_patch(
        wt,
        "darts/timeseries.py",
        """from darts.utils.utils import (
    SUPPORTED_RESAMPLE_METHODS,
    dataframe_col_to_time_index,
    expand_arr,
    generate_index,
    infer_freq_intersection,
    n_steps_between,
)""",
        """from darts.utils.step_alignment import intersect_shift_start
from darts.utils.utils import (
    SUPPORTED_RESAMPLE_METHODS,
    dataframe_col_to_time_index,
    expand_arr,
    generate_index,
    infer_freq_intersection,
    n_steps_between,
)""",
    )
    apply_text_patch(
        wt,
        "darts/utils/historical_forecasts/utils.py",
        """        missing_steps = n_steps_between(
            hfcs_[-1].end_time(), series[0].end_time(), freq=series[0].freq
        )""",
        """        missing_steps = missing_target_steps_after_forecast(
            forecast_end=hfcs_[-1].end_time(),
            target_end=series[0].end_time(),
            freq=series[0].freq,
        )""",
    )


def bug_darts(c: Path) -> None:
    apply_text_patch(
        c,
        "darts/utils/historical_forecasts/utils.py",
        "        train_length_adjusted = train_length + start_shifted\n",
        "        train_length_adjusted = train_length + start_shifted + 1\n",
    )


def bug_stylelint(c: Path) -> None:
    apply_text_patch(
        c,
        "lib/utils/rangesOverlap.mjs",
        "if (a[1] <= b[0]) return false;",
        "if (a[1] < b[0]) return false;",
    )
    apply_text_patch(
        c,
        "lib/utils/narrowFixRange.mjs",
        "\t\t\treplacementEndOffset++;",
        "\t\t\treplacementEndOffset = fixData.text.length;",
    )


def bug_recharts(c: Path) -> None:
    apply_text_patch(
        c,
        "src/util/tooltip/translate.ts",
        """    if (tooltipBoundary < viewBoxBoundary) {
      return Math.max(negative, viewBoxKey);
    }""",
        """    if (tooltipBoundary < viewBoxBoundary) {
      return Math.max(positive, viewBoxKey);
    }""",
    )
    apply_text_patch(
        c,
        "src/component/TooltipBoundingBox.tsx",
        "    viewBox: props.viewBox,",
        "    viewBox: { ...props.viewBox, width: props.viewBox.width + 40 },",
    )


LH_PATCHES: dict[str, dict] = {
    "albumentations": {
        "apply_bug": noop_bug,
        "apply_fix": fix_albumentations,
        "instruction": (
            "Crop transforms must keep bounding boxes, keypoints, and crop-and-pad bbox pipelines "
            "consistent: annotations that fall completely outside the crop region should be removed, "
            "partial overlaps must be clipped to the crop rectangle, and the transform layer must "
            "preserve normalized versus absolute coordinate modes. Shared crop-space clipping logic "
            "should live in one place and be reused rather than reimplemented per helper."
        ),
        "one_sentence": (
            "Unify crop-space clipping for bboxes, keypoints, and crop-and-pad bbox paths using "
            "shared helpers and correct normalized-input handling in crop transforms."
        ),
        "why_worth_using": (
            "Models patch one helper or clip after normalize; mixed batches, keypoints, "
            "crop-and-pad, and transform wiring expose partial fixes."
        ),
        "rubric_correctness": (
            "- Shared crop-space clip+filter helper used by bbox paths.\n"
            "- Keypoints clipped and filtered to crop canvas.\n"
            "- Crop transforms pass normalized_input correctly.\n"
            "- pass2pass core utils stay green."
        ),
        "test_files": {
            "tests/test_crop_lh_matrix.py": """
                from __future__ import annotations
                import numpy as np
                import pytest
                from albumentations.augmentations.crops.functional import (
                    crop_and_pad_bboxes,
                    crop_bboxes_by_coords,
                    crop_keypoints_by_coords,
                )

                def test_crop_and_pad_clips_partial():
                    bboxes = np.array([[0.4, 0.4, 0.8, 0.8]], dtype=np.float32)
                    crop = (0, 0, 50, 50)
                    out = crop_and_pad_bboxes(bboxes, crop, None, (100, 100), (50, 50))
                    np.testing.assert_allclose(
                        out, np.array([[0.8, 0.8, 1.0, 1.0]], dtype=np.float32), rtol=1e-5
                    )

                def test_keypoints_outside_removed():
                    kps = np.array([[60.0, 60.0, 0.0, 0.0], [10.0, 10.0, 0.0, 0.0]], dtype=np.float32)
                    out = crop_keypoints_by_coords(kps, (0, 0, 50, 50))
                    assert out.shape == (1, 4)
                    np.testing.assert_allclose(out[0, :2], [10.0, 10.0])

                @pytest.mark.parametrize(
                    "bboxes, crop_coords, image_shape, expected",
                    [
                        (np.array([[0.8, 0.8, 0.9, 0.9]], dtype=np.float32), (0, 0, 50, 50), (100, 100), np.zeros((0, 4), dtype=np.float32)),
                        (np.array([[0.4, 0.4, 0.8, 0.8]], dtype=np.float32), (0, 0, 50, 50), (100, 100), np.array([[0.8, 0.8, 1.0, 1.0]], dtype=np.float32)),
                        (np.array([[40.0, 40.0, 80.0, 80.0]], dtype=np.float32), (0, 0, 50, 50), (100, 100), np.array([[40.0, 40.0, 50.0, 50.0]], dtype=np.float32)),
                    ],
                )
                def test_crop_bboxes_matrix(bboxes, crop_coords, image_shape, expected):
                    norm = bboxes[0, 0] <= 1.0
                    result = crop_bboxes_by_coords(bboxes, crop_coords, image_shape, normalized_input=norm)
                    if expected.size == 0:
                        assert result.shape == (0, bboxes.shape[1])
                    else:
                        np.testing.assert_allclose(result, expected, rtol=1e-5, atol=1e-5)
            """,
        },
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\nrm -f tests/test_crop_lh_matrix.py tests/test_crop_bboxes_clipping.py\n"
            "export NO_ALBUMENTATIONS_UPDATE=1\nexport PYTHONPATH=/testbed\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "pytest tests/test_crop_lh_matrix.py tests/test_core_utils.py -q&&pass||fail\n"
        ),
    },
    "stylelint": {
        "apply_bug": bug_stylelint,
        "apply_fix": fix_stylelint,
        "instruction": (
            "Autofix edit-info recording drops valid fixes and mis-aligns replacement slices. "
            "Deduplication must use the smallest source span after narrowing, not whole-node "
            "spans; endpoint-adjacent offset ranges must not count as overlapping; and zero-width "
            "range expansion must keep replacement text aligned with the narrowed span."
        ),
        "one_sentence": (
            "Fix autofix edit-info deduplication: overlap checks on narrowed ranges, "
            "endpoint-adjacent ranges non-overlapping, and zero-width range suffix alignment."
        ),
        "why_worth_using": (
            "Spans report wiring, overlap helpers, and range narrowing; partial fixes drop valid "
            "edits or corrupt replacement slices."
        ),
        "rubric_correctness": (
            "- Overlap checked after narrowing on fixData.range.\n"
            "- Endpoint-adjacent ranges non-overlapping.\n"
            "- Zero-width range expansion keeps replacement text aligned.\n"
            "- Existing rangesOverlap and narrowFixRange tests stay green."
        ),
        "test_files": {
            "lib/utils/__tests__/editInfoPipelineSeeded.test.mjs": """
                import postcss from 'postcss';

                import editInfoOverlap from '../editInfoOverlap.mjs';
                import narrowFixRange from '../narrowFixRange.mjs';
                import recordFixEditInfo from '../recordFixEditInfo.mjs';
                import rangesOverlap from '../rangesOverlap.mjs';

                function applyFixData(originalText, replacementText, range) {
                  const prefix = originalText.slice(0, range[0]);
                  const suffix = originalText.slice(range[1]);
                  return prefix + replacementText + suffix;
                }

                describe('edit-info pipeline seeded', () => {
                  test('editInfoOverlap treats endpoint-adjacent ranges as non-overlapping', () => {
                    expect(editInfoOverlap([[1, 2], [5, 10]], [2, 3])).toBe(false);
                  });

                  test('editInfoOverlap detects interior overlap against recorded ranges', () => {
                    expect(editInfoOverlap([[1, 2], [5, 10]], [1, 3])).toBe(true);
                  });

                  test('editInfoOverlap allows a candidate between recorded ranges', () => {
                    expect(editInfoOverlap([[1, 2], [8, 10]], [3, 4])).toBe(false);
                  });

                  test('editInfoOverlap treats zero-width boundary touch as non-overlapping', () => {
                    expect(editInfoOverlap([[5, 10]], [10, 10])).toBe(false);
                  });

                  test('rangesOverlap treats touching endpoint ranges as non-overlapping', () => {
                    expect(rangesOverlap([1, 2], [2, 3])).toBe(false);
                  });

                  test('recordFixEditInfo records a narrowed fix and pushes its range', () => {
                    const root = postcss.parse('a { color: red; top: 0px }');
                    const colorDecl = root.first.first;
                    const recorded = [];
                    const result = { opts: {} };

                    const fixData = recordFixEditInfo({
                      apply: () => {
                        colorDecl.value = 'blue';
                      },
                      node: colorDecl,
                      fixedNodeRange: [colorDecl.source.start.offset, colorDecl.source.end.offset],
                      rangesOfComputedEditInfos: recorded,
                      result,
                    });

                    expect(fixData).toBeDefined();
                    expect(recorded).toEqual([fixData.range]);
                  });

                  test('recordFixEditInfo suppresses duplicate fixes after narrowing', () => {
                    const root = postcss.parse('a { color: red; top: 0px }');
                    const colorDecl = root.first.first;
                    const recorded = [[11, 14]];
                    const result = { opts: {} };

                    const fixData = recordFixEditInfo({
                      apply: () => {
                        colorDecl.value = 'reed';
                      },
                      node: colorDecl,
                      fixedNodeRange: [colorDecl.source.start.offset, colorDecl.source.end.offset],
                      rangesOfComputedEditInfos: recorded,
                      result,
                    });

                    expect(fixData).toBeUndefined();
                    expect(recorded).toEqual([[11, 14]]);
                  });

                  test('recordFixEditInfo deduplicates using narrowed spans not whole-node ranges', () => {
                    const root = postcss.parse('a { color: red; top: 0px }');
                    const rule = root.first;
                    const topDecl = rule.first.next();
                    const recorded = [[11, 14]];
                    const result = { opts: {} };

                    const fixData = recordFixEditInfo({
                      apply: () => {
                        topDecl.value = '1px';
                      },
                      node: rule,
                      fixedNodeRange: [rule.source.start.offset, rule.source.end.offset],
                      rangesOfComputedEditInfos: recorded,
                      result,
                    });

                    expect(fixData).toBeDefined();
                    expect(recorded).toHaveLength(2);
                  });

                  test('zero-width range expansion keeps replacement text aligned', () => {
                    const node = postcss.parse('oo {}').first;
                    const fixData = {
                      range: [node.source.start?.offset, node.source.end?.offset],
                      text: 'foo {}',
                    };

                    const narrowRange = narrowFixRange(node, fixData);

                    expect(narrowRange).toMatchObject({
                      range: [0, 1],
                      text: 'fo',
                    });
                    expect(applyFixData('oo {}', narrowRange.text, narrowRange.range)).toBe('foo {}');
                  });
                });
            """,
        },
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\nrm -f lib/utils/__tests__/editInfoPipelineSeeded.test.mjs\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "npm run test-only -- lib/utils/__tests__/editInfoPipelineSeeded.test.mjs "
            "lib/utils/__tests__/rangesOverlap.test.mjs "
            "lib/utils/__tests__/narrowFixRange.test.mjs&&pass||fail\n"
        ),
    },
    "recharts": {
        "apply_bug": bug_recharts,
        "apply_fix": fix_recharts,
        "instruction": (
            "Cartesian chart tooltips clip inside the drawable plot area when view-box escape is "
            "disabled. Overflow on either axis should flip to the far side of the anchor, wrapper "
            "CSS direction classes must match the final translate against the anchor (including "
            "axis-equal edge cases), and the placement pipeline must feed the plot-area bounds "
            "through to the translate helper without ad-hoc dimension inflation or full-chart "
            "container bounds."
        ),
        "one_sentence": (
            "Fix tooltip in-plot clipping: axis overflow flip, direction CSS classes, and "
            "plot-area view-box wiring end-to-end."
        ),
        "why_worth_using": (
            "Translate math, bounding-box wiring, and selector/context hooks must agree; "
            "translate-only or padding-hack fixes leave mis-placed or mis-labeled tooltips."
        ),
        "rubric_correctness": (
            "- Overflow flips to negative side on x and y (incl. reverseDirection).\n"
            "- CSS top/bottom/left/right classes match strict translate vs anchor.\n"
            "- Plot-area viewBox wired without width fudge or axis container bounds.\n"
            "- Existing translate.spec.ts stays green."
        ),
        "test_files": {
            "test/util/tooltipLongHorizonSeeded.spec.ts": """
                import React from 'react';
                import { render, screen } from '@testing-library/react';
                import { TooltipBoundingBox } from '../../src/component/TooltipBoundingBox';
                import {
                  getTooltipCSSClassName,
                  getTooltipTranslate,
                  getTooltipTranslateXY,
                } from '../../src/util/tooltip/translate';

                describe('tooltip long-horizon seeded', () => {
                  const plotViewBox = { x: 50, y: 20, width: 250, height: 180 };
                  const axisViewBox = { x: 0, y: 0, width: 400, height: 260 };
                  const allowEscape = { x: false, y: false };
                  const reverseOff = { x: false, y: false };

                  it('flips on horizontal overflow inside plot viewBox', () => {
                    const x = getTooltipTranslateXY({
                      allowEscapeViewBox: allowEscape,
                      coordinate: { x: 280, y: 100 },
                      key: 'x',
                      offset: 10,
                      position: undefined,
                      reverseDirection: reverseOff,
                      tooltipDimension: 60,
                      viewBox: plotViewBox,
                      viewBoxDimension: plotViewBox.width,
                    });
                    expect(x).toBeLessThan(280);
                  });

                  it('flips on vertical overflow inside plot viewBox', () => {
                    const y = getTooltipTranslateXY({
                      allowEscapeViewBox: allowEscape,
                      coordinate: { x: 100, y: 175 },
                      key: 'y',
                      offset: 8,
                      position: undefined,
                      reverseDirection: reverseOff,
                      tooltipDimension: 45,
                      viewBox: plotViewBox,
                      viewBoxDimension: plotViewBox.height,
                    });
                    expect(y).toBeLessThan(175);
                  });

                  it('assigns top CSS class when translateY is at or above anchor', () => {
                    const cls = getTooltipCSSClassName({
                      translateX: 120,
                      translateY: 50,
                      coordinate: { x: 120, y: 50 },
                    });
                    expect(cls).toContain('recharts-tooltip-wrapper-top');
                    expect(cls).not.toContain('recharts-tooltip-wrapper-bottom');
                  });

                  it('assigns bottom CSS class when translateY is below anchor', () => {
                    const cls = getTooltipCSSClassName({
                      translateX: 120,
                      translateY: 80,
                      coordinate: { x: 120, y: 50 },
                    });
                    expect(cls).toContain('recharts-tooltip-wrapper-bottom');
                  });

                  it('reverseDirection flips to positive side when negative placement escapes', () => {
                    const x = getTooltipTranslateXY({
                      allowEscapeViewBox: allowEscape,
                      coordinate: { x: 30, y: 100 },
                      key: 'x',
                      offset: 5,
                      position: undefined,
                      reverseDirection: { x: true, y: false },
                      tooltipDimension: 50,
                      viewBox: { x: 10, y: 20, width: 250, height: 180 },
                      viewBoxDimension: 250,
                    });
                    expect(x).toBeGreaterThanOrEqual(10);
                    expect(x).toBeLessThan(30);
                  });

                  it('plot viewBox triggers flip where full container bounds would not', () => {
                    const args = {
                      allowEscapeViewBox: allowEscape,
                      coordinate: { x: 280, y: 100 },
                      key: 'x' as const,
                      offset: 10,
                      position: undefined,
                      reverseDirection: reverseOff,
                      tooltipDimension: 60,
                    };
                    const withPlot = getTooltipTranslateXY({
                      ...args,
                      viewBox: plotViewBox,
                      viewBoxDimension: plotViewBox.width,
                    });
                    const withAxis = getTooltipTranslateXY({
                      ...args,
                      viewBox: axisViewBox,
                      viewBoxDimension: axisViewBox.width,
                    });
                    expect(withPlot).toBeLessThan(280);
                    expect(withAxis).toBeGreaterThan(280);
                  });

                  it('width inflation prevents horizontal flip detection', () => {
                    const base = {
                      allowEscapeViewBox: allowEscape,
                      coordinate: { x: 170, y: 50 },
                      key: 'x' as const,
                      offset: 10,
                      position: undefined,
                      reverseDirection: reverseOff,
                      tooltipDimension: 50,
                    };
                    const plotWidth = 200;
                    const correct = getTooltipTranslateXY({
                      ...base,
                      viewBox: { x: 0, y: 0, width: plotWidth, height: 100 },
                      viewBoxDimension: plotWidth,
                    });
                    const inflated = getTooltipTranslateXY({
                      ...base,
                      viewBox: { x: 0, y: 0, width: plotWidth + 40, height: 100 },
                      viewBoxDimension: plotWidth + 40,
                    });
                    expect(correct).toBeLessThan(170);
                    expect(inflated).toBeGreaterThanOrEqual(180);
                  });

                  it('getTooltipTranslate flips both axes inside plot bounds', () => {
                    const { cssProperties, cssClasses } = getTooltipTranslate({
                      allowEscapeViewBox: allowEscape,
                      coordinate: { x: 280, y: 175 },
                      offsetTop: 8,
                      offsetLeft: 10,
                      position: undefined,
                      reverseDirection: reverseOff,
                      tooltipBox: { width: 60, height: 45 },
                      useTranslate3d: false,
                      viewBox: plotViewBox,
                    });
                    const match = cssProperties.transform?.match(/translate\\((\\d+)px, (\\d+)px\\)/);
                    expect(match).not.toBeNull();
                    expect(Number(match![1])).toBeLessThan(280);
                    expect(Number(match![2])).toBeLessThan(175);
                    expect(cssClasses).toContain('recharts-tooltip-wrapper-left');
                    expect(cssClasses).toContain('recharts-tooltip-wrapper-top');
                  });

                  it('TooltipBoundingBox does not inflate viewBox width before translate', () => {
                    render(
                      React.createElement(TooltipBoundingBox, {
                        innerRef: () => {},
                        lastBoundingBox: { width: 50, height: 40, left: 0, top: 0 },
                        active: true,
                        hasPayload: true,
                        coordinate: { x: 170, y: 50 },
                        allowEscapeViewBox: allowEscape,
                        animationDuration: 0,
                        animationEasing: 'ease',
                        isAnimationActive: false,
                        offset: 10,
                        position: undefined,
                        reverseDirection: reverseOff,
                        useTranslate3d: false,
                        viewBox: { x: 0, y: 0, width: 200, height: 100 },
                        wrapperStyle: {},
                        hasPortalFromProps: false,
                      }, 'tooltip-body'),
                    );
                    const el = screen.getByText('tooltip-body');
                    const transform = el.style.transform;
                    const match = transform.match(/translate\\((\\d+)px/);
                    expect(match).not.toBeNull();
                    expect(Number(match![1])).toBeLessThan(170);
                  });

                  it('exports plot-area view box hook for tooltip placement', async () => {
                    const ctx = await import('../../src/context/chartLayoutContext');
                    expect(typeof ctx.useTooltipPlotViewBox).toBe('function');
                  });
                });
            """,
        },
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\nrm -f test/util/tooltipLongHorizonSeeded.spec.ts test/util/getTooltipTranslateSeeded.spec.ts\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "npm run test -- test/util/tooltipLongHorizonSeeded.spec.ts test/util/tooltip/translate.spec.ts&&pass||fail\n"
        ),
    },
    "vercel-ai": {
        "apply_bug": bug_vercel_ai,
        "apply_fix": fix_vercel_ai,
        "instruction": (
            "When chat completion streams emit tool-call deltas, each new call must occupy its "
            "own slot even when the provider omits the chunk index, partial deltas that lack "
            "enough metadata to start a call must be held until a name is known, and anything "
            "still buffered when the stream ends must be finalized consistently across the shared "
            "streaming helper and the provider adapters that consume it."
        ),
        "one_sentence": (
            "Fix streaming tool-call slot allocation, index synthesis, and pending-buffer flush "
            "across the shared helper and chat-completion adapters."
        ),
        "why_worth_using": (
            "The shared streaming helper and multiple chat-completion adapters must agree on "
            "index synthesis and flush semantics; fixing only one layer still corrupts "
            "multi-tool streams."
        ),
        "rubric_correctness": (
            "- Unindexed sequential deltas create separate tool calls.\n"
            "- Adapters synthesize a stable slot when index is missing.\n"
            "- Partial deltas buffer until function metadata is complete.\n"
            "- Stream flush forwards pending calls with id/type/name.\n"
            "- Existing tracker unit tests stay green."
        ),
        "dockerfile": """FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
RUN npm install -g pnpm@10
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN pnpm install --filter @ai-sdk/groq... --filter @ai-sdk/openai-compatible... --filter @ai-sdk/test-server... --frozen-lockfile || pnpm install --filter @ai-sdk/groq... --filter @ai-sdk/openai-compatible... --filter @ai-sdk/test-server...
RUN pnpm --filter @ai-sdk/provider build && pnpm --filter @ai-sdk/provider-utils build && pnpm --filter @ai-sdk/test-server build && pnpm --filter @ai-sdk/openai-compatible build && pnpm --filter @ai-sdk/groq build
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_files": {
            "packages/provider-utils/src/streaming-tool-call-tracker-lh.test.ts": """
                import { describe, expect, it } from 'vitest';
                import { StreamingToolCallTracker } from './streaming-tool-call-tracker';

                function collectStarts() {
                  const starts: Array<{ id: string; toolName: string }> = [];
                  const controller = {
                    enqueue: (e: { type: string; id?: string; toolName?: string }) => {
                      if (e.type === 'tool-input-start' && e.id && e.toolName) {
                        starts.push({ id: e.id, toolName: e.toolName });
                      }
                    },
                  };
                  return { starts, tracker: new StreamingToolCallTracker(controller as never) };
                }

                describe('streaming tool call LH seeded — tracker', () => {
                  it('allocates separate slots for sequential unnamed deltas', () => {
                    const { starts, tracker } = collectStarts();
                    tracker.processDelta({
                      id: 'a',
                      type: 'function',
                      function: { name: 'one', arguments: '{}' },
                    });
                    tracker.processDelta({
                      id: 'b',
                      type: 'function',
                      function: { name: 'two', arguments: '{}' },
                    });
                    tracker.flush();
                    expect(starts.map(s => s.id)).toEqual(['a', 'b']);
                  });

                  it('merges argument chunks for the same explicit index', () => {
                    const events: string[] = [];
                    const controller = {
                      enqueue: (e: { type: string; delta?: string }) => {
                        if (e.type === 'tool-input-delta' && e.delta) events.push(e.delta);
                      },
                    };
                    const tracker = new StreamingToolCallTracker(controller as never);
                    tracker.processDelta({
                      index: 0,
                      id: 'c1',
                      type: 'function',
                      function: { name: 'merge', arguments: '{"part":' },
                    });
                    tracker.processDelta({
                      index: 0,
                      function: { arguments: '1}' },
                    });
                    tracker.flush();
                    expect(events.join('')).toBe('{"part":1}');
                  });

                  it('keeps interleaved explicit-index tool calls isolated', () => {
                    const { starts, tracker } = collectStarts();
                    tracker.processDelta({
                      index: 0,
                      id: 'left',
                      type: 'function',
                      function: { name: 'alpha', arguments: '{"a":1}' },
                    });
                    tracker.processDelta({
                      index: 1,
                      id: 'right',
                      type: 'function',
                      function: { name: 'beta', arguments: '{"b":2}' },
                    });
                    tracker.flush();
                    expect(starts).toEqual([
                      { id: 'left', toolName: 'alpha' },
                      { id: 'right', toolName: 'beta' },
                    ]);
                  });

                  it('appends a third unnamed delta after two indexed calls', () => {
                    const { starts, tracker } = collectStarts();
                    tracker.processDelta({
                      index: 0,
                      id: 'i0',
                      type: 'function',
                      function: { name: 'first', arguments: '{}' },
                    });
                    tracker.processDelta({
                      index: 1,
                      id: 'i1',
                      type: 'function',
                      function: { name: 'second', arguments: '{}' },
                    });
                    tracker.processDelta({
                      id: 'tail',
                      type: 'function',
                      function: { name: 'third', arguments: '{}' },
                    });
                    tracker.flush();
                    expect(starts.map(s => s.toolName)).toEqual(['first', 'second', 'third']);
                  });

                  it('flush finalizes a single incomplete tool call', () => {
                    const events: Array<{ type: string; toolCallId?: string }> = [];
                    const controller = {
                      enqueue: (e: { type: string; toolCallId?: string }) => events.push(e),
                    };
                    const tracker = new StreamingToolCallTracker(controller as never);
                    tracker.processDelta({
                      index: 0,
                      id: 'partial',
                      type: 'function',
                      function: { name: 'fn', arguments: '{"x":' },
                    });
                    tracker.flush();
                    expect(
                      events.some(e => e.type === 'tool-call' && e.toolCallId === 'partial'),
                    ).toBe(true);
                  });
                });
            """,
            "packages/openai-compatible/src/chat/openai-compatible-tool-call-lh.test.ts": """
                import { describe, expect, it } from 'vitest';
                import type { LanguageModelV4Prompt } from '@ai-sdk/provider';
                import { createTestServer } from '@ai-sdk/test-server/with-vitest';
                import { convertReadableStreamToArray } from '@ai-sdk/provider-utils/test';
                import { createOpenAICompatible } from '../openai-compatible-provider';

                const TEST_PROMPT: LanguageModelV4Prompt = [
                  { role: 'user', content: [{ type: 'text', text: 'Hello' }] },
                ];
                const TOOL = {
                  type: 'function' as const,
                  name: 'lh-tool',
                  inputSchema: {
                    type: 'object',
                    properties: { value: { type: 'string' } },
                    required: ['value'],
                    additionalProperties: false,
                    $schema: 'http://json-schema.org/draft-07/schema#',
                  },
                };
                const provider = createOpenAICompatible({
                  baseURL: 'https://my.api.com/v1/',
                  name: 'lh-provider',
                  headers: { Authorization: 'Bearer test-api-key' },
                });
                const model = provider('grok-3');
                const URL = 'https://my.api.com/v1/chat/completions';
                const server = createTestServer({ [URL]: {} });

                describe('openai-compatible tool call LH seeded', () => {
                  it('assigns distinct slots to sequential null-index tool calls', async () => {
                    server.urls[URL].response = {
                      type: 'stream-chunks',
                      chunks: [
                        `data: {"id":"lh-2","object":"chat.completion.chunk","created":1,"model":"grok-3","choices":[{"index":0,"delta":{"tool_calls":[{"id":"n0","type":"function","function":{"name":"alpha","arguments":"{}"}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"lh-2","object":"chat.completion.chunk","created":1,"model":"grok-3","choices":[{"index":0,"delta":{"tool_calls":[{"id":"n1","type":"function","function":{"name":"beta","arguments":"{}"}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"lh-2","object":"chat.completion.chunk","created":1,"model":"grok-3","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\\n\\n`,
                        'data: [DONE]\\n\\n',
                      ],
                    };
                    const { stream } = await model.doStream({ prompt: TEST_PROMPT, tools: [TOOL] });
                    const parts = await convertReadableStreamToArray(stream);
                    const starts = parts.filter(p => p.type === 'tool-input-start');
                    expect(starts.map(s => (s as { toolName: string }).toolName)).toEqual([
                      'alpha',
                      'beta',
                    ]);
                  });
                });
            """,
            "packages/groq/src/groq-tool-call-lh.test.ts": """
                import { describe, expect, it, vi } from 'vitest';
                import type { LanguageModelV4Prompt } from '@ai-sdk/provider';
                import { createTestServer } from '@ai-sdk/test-server/with-vitest';
                import { convertReadableStreamToArray } from '@ai-sdk/provider-utils/test';
                import { createGroq } from './groq-provider';

                vi.mock('./version', () => ({ VERSION: '0.0.0-test' }));

                const TEST_PROMPT: LanguageModelV4Prompt = [
                  { role: 'user', content: [{ type: 'text', text: 'Hello' }] },
                ];
                const TOOL = {
                  type: 'function' as const,
                  name: 'groq-tool',
                  inputSchema: {
                    type: 'object',
                    properties: { q: { type: 'string' } },
                    required: ['q'],
                    additionalProperties: false,
                    $schema: 'http://json-schema.org/draft-07/schema#',
                  },
                };
                const URL = 'https://api.groq.com/openai/v1/chat/completions';
                const provider = createGroq({ apiKey: 'test-api-key' });
                const model = provider('gemma2-9b-it');
                const server = createTestServer({ [URL]: {} });

                describe('groq tool call LH seeded', () => {
                  it('buffers indexed delta until function.name arrives', async () => {
                    server.urls[URL].response = {
                      type: 'stream-chunks',
                      chunks: [
                        `data: {"id":"g-1","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"g-late","type":"function","function":{"arguments":""}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-1","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"g-late","type":"function","function":{"name":"groq-tool","arguments":"{}"}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-1","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\\n\\n`,
                        'data: [DONE]\\n\\n',
                      ],
                    };
                    const { stream } = await model.doStream({ prompt: TEST_PROMPT, tools: [TOOL] });
                    const parts = await convertReadableStreamToArray(stream);
                    const starts = parts.filter(p => p.type === 'tool-input-start');
                    expect(starts).toHaveLength(1);
                    expect(starts[0]).toMatchObject({ id: 'g-late', toolName: 'groq-tool' });
                  });

                  it('assigns distinct slots to sequential null-index tool calls', async () => {
                    server.urls[URL].response = {
                      type: 'stream-chunks',
                      chunks: [
                        `data: {"id":"g-2","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"g0","type":"function","function":{"name":"alpha","arguments":"{}"}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-2","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":1,"id":"g1","type":"function","function":{"name":"beta","arguments":"{}"}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-2","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\\n\\n`,
                        'data: [DONE]\\n\\n',
                      ],
                    };
                    const { stream } = await model.doStream({ prompt: TEST_PROMPT, tools: [TOOL] });
                    const parts = await convertReadableStreamToArray(stream);
                    const starts = parts.filter(p => p.type === 'tool-input-start');
                    expect(starts.map(s => (s as { toolName: string }).toolName)).toEqual([
                      'alpha',
                      'beta',
                    ]);
                  });

                  it('drains pending buffers on stream flush when name never arrives', async () => {
                    server.urls[URL].response = {
                      type: 'stream-chunks',
                      chunks: [
                        `data: {"id":"g-3","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"orphan","type":"function","function":{"arguments":""}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-3","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\\n\\n`,
                        'data: [DONE]\\n\\n',
                      ],
                    };
                    const { stream } = await model.doStream({ prompt: TEST_PROMPT, tools: [TOOL] });
                    await expect(convertReadableStreamToArray(stream)).rejects.toThrow(
                      /function\\.name/,
                    );
                  });

                  it('isolates interleaved indexed pending buffers', async () => {
                    server.urls[URL].response = {
                      type: 'stream-chunks',
                      chunks: [
                        `data: {"id":"g-4","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"ga","type":"function","function":{"arguments":""}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-4","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":1,"id":"gb","type":"function","function":{"arguments":""}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-4","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"name":"groq-tool","arguments":"{}"}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-4","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{"tool_calls":[{"index":1,"function":{"name":"groq-tool","arguments":"{}"}}]},"finish_reason":null}]}\\n\\n`,
                        `data: {"id":"g-4","object":"chat.completion.chunk","created":1,"model":"gemma2-9b-it","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\\n\\n`,
                        'data: [DONE]\\n\\n',
                      ],
                    };
                    const { stream } = await model.doStream({ prompt: TEST_PROMPT, tools: [TOOL] });
                    const parts = await convertReadableStreamToArray(stream);
                    const calls = parts.filter(p => p.type === 'tool-call');
                    expect(calls.map(c => (c as { input: string }).input)).toEqual(['{}', '{}']);
                  });
                });
            """,
        },
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\n"
            "rm -f packages/provider-utils/src/streaming-tool-call-tracker-lh.test.ts "
            "packages/provider-utils/src/streaming-tool-call-tracker-seeded.test.ts "
            "packages/openai-compatible/src/chat/openai-compatible-tool-call-lh.test.ts "
            "packages/groq/src/groq-tool-call-lh.test.ts\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "pnpm --filter @ai-sdk/provider-utils build&&pnpm --filter @ai-sdk/openai-compatible build&&pnpm --filter @ai-sdk/groq build||fail\n"
            "cd packages/provider-utils&&pnpm test:node streaming-tool-call-tracker-lh streaming-tool-call-tracker||fail\n"
            "cd ../openai-compatible&&pnpm test:node openai-compatible-tool-call-lh||fail\n"
            "cd ../groq&&pnpm test:node groq-tool-call-lh||fail\n"
            "pass\n"
        ),
    },
    "darts": {
        "apply_bug": bug_darts,
        "apply_fix": fix_darts,
        "instruction": (
            "Integer step counting between indices must return zero when start equals end, "
            "historical-forecast train-length adjustment must not add spurious steps when the "
            "shift is zero or negative, and covariate/target index alignment must use consistent "
            "start/end ordering in n_steps_between."
        ),
        "one_sentence": (
            "Fix zero-span step counting and downstream historical-forecast and dataset index math."
        ),
        "why_worth_using": (
            "n_steps_between feeds historical forecasts and tabular dataset alignment; "
            "local fixes to one caller leave window math broken elsewhere."
        ),
        "rubric_correctness": (
            "- n_steps_between(equal indices)==0.\n"
            "- train_length_adjusted uses max(0, start_shifted).\n"
            "- covariate index helper uses end/start order consistently.\n"
            "- test_config pass2pass stays green."
        ),
        "test_files": {
            "darts/tests/utils/test_lh_steps_pipeline.py": """
                from darts.utils.utils import n_steps_between
                from darts.utils.data import utils as data_utils
                from darts import TimeSeries
                import pandas as pd

                def test_zero_span_integer():
                    assert n_steps_between(end=2, start=2, freq=1) == 0

                def test_covariate_index_alignment():
                    idx = pd.date_range("2020-01-01", periods=5, freq="D")
                    target = TimeSeries.from_times_and_values(idx, [1, 2, 3, 4, 5])
                    cov = TimeSeries.from_times_and_values(idx, [1, 2, 3, 4, 5])
                    assert data_utils._get_matching_index(target, cov, 4) == 4
            """,
        },
        "test_header": (
            "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\n"
            "fail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\n"
            "pass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\n"
            "cd /testbed||fail\nrm -f darts/tests/utils/test_lh_steps_pipeline.py darts/tests/utils/test_n_steps_seeded.py\n"
        ),
        "test_footer": (
            "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n"
            "pytest darts/tests/utils/test_lh_steps_pipeline.py darts/tests/test_config.py -q&&pass||fail\n"
        ),
    },
}


def apply_lh(slug: str) -> None:
    if slug not in LH_PATCHES:
        raise SystemExit(f"no long-horizon override for {slug}")
    base = ALL_TASKS[slug]
    ALL_TASKS[slug] = {**base, **LH_PATCHES[slug]}
    build_one(slug, ALL_TASKS[slug])


if __name__ == "__main__":
    slugs = sys.argv[1:] if len(sys.argv) > 1 else list(LH_PATCHES.keys())
    for s in slugs:
        print(f"=== long-horizon build: {s} ===")
        apply_lh(s)
