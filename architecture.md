# Duetto System Architecture

This document outlines the modular architecture of the Duetto monitoring system.

## 1. High-Level Overview

Duetto follows a **Pipeline Architecture**:
`Collectors` -> `Engine` -> `Processors` -> `Engine` -> `Notifiers`

*   **Collectors**: Fetch raw data from external sources (SEC, FDA, TradingView).
*   **Engine**: The central nervous system that runs collectors and routes alerts.
*   **Processors**: Clean, filter, duplicate-check, and enrich alerts.
*   **Notifiers**: Format and deliver alerts to external channels (Feishu, Telegram, etc.).

## 2. Core Modules

### 2.1 Engine (`duetto/engine.py`)
**Role**: Orchestrator.
**Implementation**:
*   `DuettoEngine` initializes with a list of Collectors, a Processing Pipeline, and Notifiers.
*   **Loop**: It launches a background asyncio task for each Collector.
*   **Routing**: As Collectors yield `Alert` objects, the Engine passes them sequentially to the `ProcessorPipeline`.
*   **Delivery**: If an Alert survives the pipeline (isn't returned as `None`), the Engine broadcasts it to the Web/UI via `WebSocketManager` and sends it to all configured Notifiers.

### 2.2 Server (`duetto/server.py`)
**Role**: API and Real-time Frontend Interface.
**Implementation**:
*   Uses **FastAPI** to serve HTTP endpoints (future extension) and WebSockets.
*   `WebSocketManager`: Maintains list of active UI clients.
*   `broadcast(alert)`: Pushes new alerts to the frontend in real-time.

### 2.3 Schemas (`duetto/schemas.py`)
**Role**: Data definition (The "Language" of Duetto).
**Implementation**:
*   Uses **Pydantic** for strict type validation.
*   `Alert`: The core object flowing through the system. Contains `id`, `title`, `company`, `priority`, `raw_data`, etc.
*   `NotificationTemplate`: Standardized format for Notifiers (Title, Body, Color, Key-Value Fields).

## 3. Layer Implementations

### 3.1 Collectors (`duetto/collectors/`)
**Interface**: `BaseCollector` (must implement `collect() -> AsyncIterator[Alert]`).

| Implementation | Description | How it works |
| :--- | :--- | :--- |
| **SEC Edgar** | Monitors SEC filings (8-K, S-3). | Polls RSS feeds every X seconds. Uses `LRUCache` to ignore seen IDs. Maps CIK to Tickers. |
| **FDA** | Monitors Drug Approvals. | Scrapes FDA website HTML. Detects new approval rows. |
| **TradingView** | Real-time Stock Prices. | Connects via **WebSocket** (aiohttp). Subscribes to configured symbols. Calculates % change locally. |

### 3.2 Processors (`duetto/processors/`)
**Interface**: `BaseProcessor` (must implement `process(alert) -> Optional[Alert]`).

| Implementation | Description | How it works |
| :--- | :--- | :--- |
| **Dedup** | Prevents duplicate alerts. | Uses an in-memory `LRUCache`. If `alert.id` exists, returns `None` (drops alert). |
| **Filter** | Business Logic Filtering. | Checks `Alert.priority` against `min_priority` settings. Future: Market Cap checks. |
| **ProcessorPipeline** | Chains processors. | Sequentially runs `alert = proc.process(alert)`. If any step returns `None`, the chain stops. |

### 3.3 Notifiers (`duetto/notifiers/`)
**Interface**: `BaseNotifier` (must implement `send(template)`).

| Implementation | Description | How it works |
| :--- | :--- | :--- |
| **Base** | Standard logic. | `create_template(alert)` converts the raw Alert into a UI-friendly `NotificationTemplate`. |
| **Feishu** | Lark/Feishu Messenger. | Converts `NotificationTemplate` into **Feishu Card JSON** structure (colors, markdown, fields) and POSTs to Webhook. |

## 4. Configuration (`duetto/config.py`)
**Role**: Centralized Settings.
**Implementation**:
*   Uses `pydantic-settings`.
*   Loads from Environment Variables (`.env`).
*   **Nested Structure**: grouped by module (e.g., `settings.tv.symbols`, `settings.sec.poll_interval`).

## 5. Flow Example
1.  **TradingViewCollector** receives a WebSocket message: "AAPL dropped 15%".
2.  Creates an `Alert` (Priority: HIGH).
3.  **Engine** receives Alert.
4.  **DedupProcessor** checks ID. New? Passthrough.
5.  **FilterProcessor** checks Config (Min Priority: Medium). HIGH >= Medium? Passthrough.
6.  **Engine** calls `ws_manager.broadcast()` -> UI shows alert immediately.
7.  **Engine** calls `FeishuNotifier.send()`:
    *   Converts Alert to Template (Color: Red, Body: "AAPL dropped...").
    *   Sends HTTP POST to Feishu.
    *   User receives notification on phone.
