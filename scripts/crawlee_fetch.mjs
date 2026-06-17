import { CheerioCrawler, PlaywrightCrawler, RequestQueue, log } from "crawlee";

log.setLevel(log.LEVELS.ERROR);

function decodeArg(arg) {
  if (!arg) {
    return null;
  }
  try {
    return Buffer.from(arg, "base64").toString("utf8");
  } catch {
    return null;
  }
}

async function main() {
  const url = process.argv[2];
  const timeoutMsRaw = process.argv[3] ?? "30000";
  const headersRaw = decodeArg(process.argv[4]);

  if (!url) {
    process.stdout.write(JSON.stringify({ html: null, error: "missing url" }));
    process.exit(1);
  }

  const timeoutMs = Number.parseInt(timeoutMsRaw, 10);
  const requestHeaders = headersRaw ? JSON.parse(headersRaw) : {};

  let html = null;
  let error = null;
  const useBrowser =
    url.includes("afisha.timepad.ru") ||
    url.includes("afisha.yandex.ru");

  const queue = await RequestQueue.open();
  await queue.addRequest({
    url,
    headers: requestHeaders,
    uniqueKey: `${url}-${Date.now()}`,
  });

  const crawler = useBrowser
    ? new PlaywrightCrawler({
        requestQueue: queue,
        maxRequestsPerCrawl: 1,
        maxRequestRetries: 1,
        requestHandlerTimeoutSecs: Math.max(20, Math.ceil(timeoutMs / 1000)),
        requestHandler: async ({ page }) => {
          await page.waitForTimeout(5000);
          html = await page.content();
        },
        failedRequestHandler: async ({ error: requestError }) => {
          error = requestError ? String(requestError) : "crawlee failed request";
        },
      })
    : new CheerioCrawler({
        requestQueue: queue,
        maxRequestsPerCrawl: 1,
        maxRequestRetries: 1,
        requestHandlerTimeoutSecs: Math.max(10, Math.ceil(timeoutMs / 1000)),
        additionalMimeTypes: ["text/html", "application/xhtml+xml"],
        requestHandler: async ({ body }) => {
          html = typeof body === "string" ? body : body.toString("utf8");
        },
        failedRequestHandler: async ({ error: requestError }) => {
          error = requestError ? String(requestError) : "crawlee failed request";
        },
      });

  try {
    await crawler.run();
  } catch (runError) {
    error = String(runError);
  }

  process.stdout.write(JSON.stringify({ html, error }));
}

main().catch((error) => {
  process.stdout.write(JSON.stringify({ html: null, error: String(error) }));
  process.exit(1);
});
