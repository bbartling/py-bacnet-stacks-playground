import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.stubGlobal("crypto", {
  randomUUID: () => "test-uuid-1234",
});

const storage: Record<string, string> = {};
const sessionStorageMock = {
  getItem: (k: string) => storage[k] ?? null,
  setItem: (k: string, v: string) => {
    storage[k] = v;
  },
  removeItem: (k: string) => {
    delete storage[k];
  },
};
vi.stubGlobal("window", { sessionStorage: sessionStorageMock });

import { ApiError, apiFetch, getToken, setToken } from "./api-client";

describe("api-client", () => {
  beforeEach(() => {
    setToken(null);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches bearer token when set", async () => {
    setToken("tok123");
    await apiFetch("/api/health");
    const call = vi.mocked(fetch).mock.calls[0];
    const headers = call[1]?.headers as Headers;
    const auth =
      headers instanceof Headers
        ? headers.get("Authorization")
        : (headers as Record<string, string>).Authorization;
    expect(auth).toBe("Bearer tok123");
  });

  it("throws ApiError on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("bad", { status: 500 })),
    );
    await expect(apiFetch("/api/x")).rejects.toBeInstanceOf(ApiError);
  });

  it("getToken returns null when cleared", () => {
    setToken(null);
    expect(getToken()).toBeNull();
  });
});
