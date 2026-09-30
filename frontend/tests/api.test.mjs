import assert from "node:assert/strict";
import { test } from "node:test";
import { api, ApiError, getToken, setToken } from "../src/lib/api.ts";

test("API sends JSON and multipart correctly and preserves useful failures", async (t) => {
  const storage = new Map();
  const originalStorage = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
  });
  t.after(() => {
    if (originalStorage) Object.defineProperty(globalThis, "localStorage", originalStorage);
    else delete globalThis.localStorage;
  });

  let response = Response.json({ session_id: "session-1" });
  const fetchMock = t.mock.method(globalThis, "fetch", async () => response.clone());
  setToken("test-token");

  await api.ask("How many customers?", null);
  let [url, options] = fetchMock.mock.calls.at(-1).arguments;
  assert.equal(url, "http://localhost:8000/api/query");
  assert.equal(options.headers.get("Authorization"), "Bearer test-token");
  assert.equal(options.headers.get("Content-Type"), "application/json");
  assert.deepEqual(JSON.parse(options.body), { question: "How many customers?", session_id: null });

  const file = new File(["name\nAlice"], "customers.csv", { type: "text/csv" });
  await api.uploadDataset(file);
  [, options] = fetchMock.mock.calls.at(-1).arguments;
  assert.equal(options.headers.has("Content-Type"), false, "Browser must set the multipart boundary");
  assert.equal(await options.body.get("file").text(), "name\nAlice");

  response = Response.json({ detail: [{ msg: "Field required" }, { msg: "Invalid column" }] }, { status: 422 });
  await assert.rejects(api.listDatasets(), (error) =>
    error instanceof ApiError && error.status === 422 && error.message === "Field required; Invalid column"
  );
  response = new Response("Proxy unavailable", { status: 502, statusText: "Bad Gateway" });
  await assert.rejects(api.listDatasets(), { message: "Bad Gateway", status: 502 });
  response = Response.json({ detail: "Session expired" }, { status: 401 });
  await assert.rejects(api.me(), { message: "Session expired", status: 401 });
  assert.equal(getToken(), null);

  response = new Response(null, { status: 204 });
  assert.equal(await api.deleteDataset("dataset-1"), undefined);
});
