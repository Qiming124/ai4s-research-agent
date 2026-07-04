/** 2D loss landscape 与 SGD 轨迹交互可视化 */

import { useState } from "react";

export interface VizData {
  viz_type: "contour_2d" | "sgd_trajectory";
  axis0?: number[];
  axis1?: number[];
  z?: number[][];
  trajectories?: Array<{
    start: number[];
    path: number[][];
    losses: number[];
  }>;
}

interface LossLandscapeVizProps {
  data: VizData;
}

export function LossLandscapeViz({ data }: LossLandscapeVizProps) {
  const [hover, setHover] = useState<string | null>(null);

  if (data.viz_type === "contour_2d" && data.z && data.axis0 && data.axis1) {
    const flat = data.z.flat();
    const min = Math.min(...flat);
    const max = Math.max(...flat);
    const rows = data.z.length;
    const cols = data.z[0]?.length ?? 0;
    const size = 240;
    const cellW = size / cols;
    const cellH = size / rows;
    const x0 = data.axis0[0] ?? 0;
    const x1 = data.axis0[data.axis0.length - 1] ?? 0;
    const y0 = data.axis1[0] ?? 0;
    const y1 = data.axis1[data.axis1.length - 1] ?? 0;

    return (
      <div className="loss-landscape-viz">
        <h5>Loss Landscape (2D)</h5>
        <div className="loss-viz-wrap">
          <svg width={size} height={size} className="contour-svg" role="img" aria-label="Loss landscape">
            {data.z.map((row, i) =>
              row.map((val, j) => {
                const t = max > min ? (val - min) / (max - min) : 0;
                const gray = Math.floor(200 * (1 - t));
                return (
                  <rect
                    key={`${i}-${j}`}
                    x={j * cellW}
                    y={i * cellH}
                    width={cellW}
                    height={cellH}
                    fill={`rgb(${gray},${gray + 30},${180 + gray})`}
                    onMouseEnter={() =>
                      setHover(
                        `L(${data.axis0?.[j]?.toFixed(2)}, ${data.axis1?.[i]?.toFixed(2)}) = ${val.toFixed(4)}`,
                      )
                    }
                    onMouseLeave={() => setHover(null)}
                  />
                );
              }),
            )}
          </svg>
          <div className="loss-viz-axes">
            <span>x0: [{x0.toFixed(1)}, {x1.toFixed(1)}]</span>
            <span>x1: [{y0.toFixed(1)}, {y1.toFixed(1)}]</span>
          </div>
        </div>
        {hover && <p className="loss-viz-hover">{hover}</p>}
      </div>
    );
  }

  if (data.viz_type === "sgd_trajectory" && data.trajectories?.length) {
    return (
      <div className="loss-landscape-viz">
        <h5>SGD 轨迹</h5>
        <ul>
          {data.trajectories.map((tr, idx) => (
            <li key={idx}>
              起点 ({tr.start.join(", ")}) → {tr.path.length} 步，终 loss{" "}
              {tr.losses[tr.losses.length - 1]?.toFixed(4)}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return null;
}
