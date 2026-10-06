import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, setToken } from "@/lib/api";

const jsonRes = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("api client", () => {
  afterEach(() => { vi.restoreAllMocks(); setToken(null); });

  it("sends the bearer token and parses JSON", async () => {
    setToken("abc");
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonRes(200, { ok: 1 }));
    expect(await api("/x")).toEqual({ ok: 1 });
    expect((f.mock.calls[0][1] as any).headers.Authorization).toBe("Bearer abc");
  });

  it("maps the backend error envelope to ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonRes(404, { error: { code: "RESOURCE_NOT_FOUND", message: "Customer not found", request_id: "r1" } }));
    await expect(api("/customers/1")).rejects.toMatchObject({ status: 404, code: "RESOURCE_NOT_FOUND", message: "Customer not found", requestId: "r1" });
  });

  it("drops empty query params", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonRes(200, {}));
    await api("/leads", { params: { q: "", status: "new", page: 2, x: undefined } });
    expect(String(f.mock.calls[0][0])).toBe("/api/v1/leads?status=new&page=2");
  });

  it("tries one silent refresh on 401 then retries", async () => {
    setToken("old");
    const f = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonRes(401, { error: { code: "INVALID_TOKEN", message: "expired" } }))
      .mockResolvedValueOnce(jsonRes(200, { access_token: "new" }))
      .mockResolvedValueOnce(jsonRes(200, { data: 1 }));
    expect(await api("/me-data")).toEqual({ data: 1 });
    expect(f).toHaveBeenCalledTimes(3);
    expect(String(f.mock.calls[1][0])).toContain("/auth/refresh");
  });

  it("exposes ApiError type", () => expect(new ApiError(400, "X", "m")).toBeInstanceOf(Error));
});
