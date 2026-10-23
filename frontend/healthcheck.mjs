try {
  const response = await fetch("http://127.0.0.1:5173/", { signal: AbortSignal.timeout(3000) });
  if (!response.ok) process.exit(1);
} catch {
  process.exit(1);
}
