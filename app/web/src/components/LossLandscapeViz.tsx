/** 2D loss landscape 与 SGD 轨迹简易可视化 */

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
  if (data.viz_type === "contour_2d" && data.z && data.axis0 && data.axis1) {
    const flat = data.z.flat();
    const min = Math.min(...flat);
    const max = Math.max(...flat);
    const rows = data.z.length;
    const cols = data.z[0]?.length ?? 0;
    const cellW = 200 / cols;
    const cellH = 200 / rows;
    return (
      <div className="loss-landscape-viz">
        <h5>Loss Landscape (2D)</h5>
        <svg width={200} height={200} className="contour-svg">
          {data.z.map((row, i) =>
            row.map((val, j) => {
              const t = max > min ? (val - min) / (max - min) : 0;
              const gray = Math.floor(255 * (1 - t));
              return (
                <rect
                  key={`${i}-${j}`}
                  x={j * cellW}
                  y={i * cellH}
                  width={cellW}
                  height={cellH}
                  fill={`rgb(${gray},${gray + 20},255)`}
                />
              );
            }),
          )}
        </svg>
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
