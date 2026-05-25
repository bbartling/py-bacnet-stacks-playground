import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { logger, setLogLevel } from "./logger";

describe("logger", () => {
  beforeEach(() => {
    vi.spyOn(console, "info").mockImplementation(() => {});
    vi.spyOn(console, "debug").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
    setLogLevel("info");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("logs info at default level", () => {
    logger.info("test", "hello");
    expect(console.info).toHaveBeenCalled();
  });

  it("suppresses debug unless level set", () => {
    logger.debug("test", "hidden");
    expect(console.debug).not.toHaveBeenCalled();
    setLogLevel("debug");
    logger.debug("test", "visible");
    expect(console.debug).toHaveBeenCalled();
  });
});
