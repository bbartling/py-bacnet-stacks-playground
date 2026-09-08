# Vibe 24 Live Twin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a runnable BACnet + FastAPI HTML twin with priority-8 UI writes and a surrogate plant stepper.

**Architecture:** PointBus owns priority arrays; SurrogatePlant steps on a timer; FastAPI and BACpypes3 both talk to the bus.

**Tech stack:** Python 3.12+, FastAPI, uvicorn, BACpypes3, pytest.

## Task 1: PointBus + SurrogatePlant + tests

- Create `src/vibe24/bus.py`, `plant.py`, `points.py`, `runtime.py`
- Tests for priority and thermal direction

## Task 2: FastAPI + HTML BAS graphic

- `src/vibe24/api.py`, `static/*`
- TestClient write/relinquish

## Task 3: BACnet device bridge

- `src/vibe24/bacnet_device.py` optional `--bacnet`
- Document Linux bind; degrade gracefully if bacpypes3 bind fails

## Task 4: Package docs + CLI

- `pyproject.toml`, `AGENTS.md`, `README.md`, `scripts/run_dashboard.ps1`
