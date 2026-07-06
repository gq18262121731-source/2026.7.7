export function fallback(value?: string | number | null, empty = "暂无数据") {
  if (value === undefined || value === null || value === "") return empty;
  return String(value);
}

export function formatPercent(value?: number | null) {
  if (value === undefined || value === null) return "暂无数据";
  return `${(value * 100).toFixed(1)}%`;
}

export function absoluteAssetUrl(path: string) {
  if (path.startsWith("http")) return path;
  const base = (
    import.meta.env.VITE_MAIN_BACKEND_API_BASE ??
    `${(import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "")}/api`
  ).replace(/\/api\/?$/, "");
  return `${base}${path}`;
}

export async function makeDemoImageFile(): Promise<File> {
  const canvas = document.createElement("canvas");
  canvas.width = 320;
  canvas.height = 240;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#4d9f64";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f2cc4d";
    ctx.fillRect(120, 60, 80, 110);
    ctx.fillStyle = "#1f4f35";
    ctx.fillRect(30, 150, 250, 18);
  }
  const blob = await new Promise<Blob>((resolve) => {
    canvas.toBlob((value) => resolve(value ?? new Blob()), "image/png");
  });
  return new File([blob], "phone-followup-demo.png", { type: "image/png" });
}
