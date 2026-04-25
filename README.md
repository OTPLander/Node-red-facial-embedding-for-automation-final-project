# Face Registration System

A complete Node-RED flow for managing, storing, and reviewing facial recognition data. This system acts as a bridge between an external Python backend (handling the heavy lifting of embeddings), a local SQLite database, a modern Vue.js dashboard, and an industrial Beckhoff PLC via OPC UA.

## Architecture & Data Flow

1. **Image Reception & Pre-processing:** The system receives a raw image byte array natively from a Beckhoff PLC via OPC UA (or simulated via an `Inject` node). The payload is dynamically truncated to remove PLC zero-padding, and forwarded to an external Python Flask server via HTTP POST.
    
2. **Embedding Generation:** The Python backend calculates the facial embedding and returns it alongside a base64 encoded version of the processed face.
    
3. **Smart Duplication Check:** Node-RED queries existing embeddings from the SQLite database and runs a Cosine Distance calculation. If the face is unknown, it proceeds to registration.
    
4. **Local Storage & Database Logging:** For new faces, the base64 image is converted back to a binary buffer and saved as a `.jpg` file in a dynamically created local directory (`saved_faces`). A new record is inserted into a local SQLite database with an initial status of `pending`.
    
5. **UI Dashboard:** A Vue.js dashboard fetches all records from the SQLite database. It displays the images by serving them via a local Node-RED HTTP endpoint and allows users to update names and change the recognition status (`pending`, `identified`, `verified`, `rejected`, `blacklisted`).
    
6. **Industrial Feedback Loop:** If an incoming face matches an existing database record with a `blacklisted` status, Node-RED bypasses the UI and instantly fires an OPC UA Write command back to the PLC, toggling a memory alarm variable to trigger a response on the factory floor.
    

## Setup & Portability

This flow has been specifically designed to be portable across different Windows machines without requiring manual hardcoded path adjustments.

- **Automatic Directory Creation:** On startup, an `exec` node runs a background Windows command to ensure the `saved_faces` directory exists within the current user's profile (`%USERPROFILE%`).
    
- **Dynamic Paths:** All file operations and database queries dynamically resolve the user's home directory.
    

## Technical Decisions & Known Issues

During development, we encountered significant limitations with the official `node-red-node-sqlite` module, which led to a complete overhaul of the database handling mechanism.

### 1. The Migration to `node-red-contrib-queued-sqlite-fix`

Initially, the flow used the standard `node-red-node-sqlite` node. However, this node hardcodes the path to the `.db` file in its configuration panel.

When trying to make the flow portable by passing a relative path (e.g., `face_data.db`), the node attempted to create the database in the Node.js working directory (often `C:\Windows\System32` depending on how Node-RED was launched). This caused silent permission errors and flow crashes. The official node does not allow injecting the database path via `msg`.

**The Fix:** We migrated to `node-red-contrib-queued-sqlite-fix`. This community node allows us to pass the absolute database path dynamically through `msg.database`. By resolving the `%USERPROFILE%` path in a preceding `Function` node and passing it to the database node, we ensure the `.db` file is always safely created and read from the user's local directory, keeping the flow 100% portable.

### 2. Bug Fix: SQLite Parameter Binding Issue

We discovered a severe bug where the UI failed to load images (initially returning 404s, and later blank wrappers). Inspection of the SQLite database revealed that while new rows were being created on image arrival, all fields—including the crucial `photo_path`—were completely empty.

**Root Cause:**

When using parameterized queries (e.g., `INSERT INTO persons (...) VALUES ($fn, $ln...)`) and passing the variables via `msg.payload`, the database node silently failed to bind the parameters. Instead of throwing an error, it executed the query with null/empty values.

**The Fix:**

We bypassed the node's parameter binding engine entirely. We now construct the raw, finalized SQL query string directly inside the `Function` nodes using template literals, injecting the variables before the query reaches the SQLite node.

_Example of the fixed UPDATE query:_

```
const d = msg.payload;
const fn = d.first_name || '';
const ln = d.last_name || '';
const st = d.status || 'pending';

// Forcing the evaluation before passing it to the SQL node
msg.topic = `UPDATE persons SET first_name='${fn}', last_name='${ln}', status='${st}' WHERE id=${d.id}`;
```

This ensures that data is consistently written to the database exactly as intended, resolving all UI rendering and data persistence issues.

## Requirements

- Node-RED
    
- `@flowfuse/node-red-dashboard` (UI components)
    
- `node-red-contrib-queued-sqlite-fix` (Database handling)
    
- `node-red-contrib-iiot-opcua` (Industrial PLC communication)
    
- A running instance of the Python embedding server on port 5000 (Auto-provisioned by the flow).
    

## System Updates: Facial Recognition Logic & UI Enhancements

This document outlines the recent architectural changes made to the Face Registration System, transforming it from a simple data logger into a smart, production-ready moderation pipeline.

### 1. Smart Duplicate Detection (The Math Behind the Magic)

We implemented an interception layer before data hits the database to prevent saving multiple entries of the same person.

**The Challenge:** Initially, comparing new faces against the database using Euclidean Distance failed to recognize the same person across different photos. This occurred because the Python backend (using DeepFace/FaceNet) normalizes embeddings in a way that relies on the angle between vectors, not the absolute distance.

**The Solution:**

We replicated NumPy's mathematical logic entirely within a Node-RED JavaScript function. We replaced the Euclidean calculation with **Cosine Distance**:

```
Cosine Distance = 1 - (A · B) / (||A|| * ||B||)
```

By querying the existing SQLite embeddings and running this calculation against incoming camera frames with a strict `THRESHOLD = 0.40`, Node-RED can accurately identify duplicate faces in milliseconds without needing to make secondary API calls to the Python backend. Known faces are currently branched off for further automation (e.g., triggering alerts), while only truly unknown faces proceed to the database.

### 2. Advanced Status Workflow & Data Lifecycle

The application now features a strict moderation pipeline with 4 specific states. The Vue.js frontend dynamically manipulates the SQLite database based on these states to keep the system clean.

- **`pending`**: The default state for new faces. These are the _only_ records that appear in the main Registry UI for manual review.
    
- **`identified`**: The face belongs to a known, benign individual. Once marked, the record updates and instantly disappears from the pending queue.
    
- **`blacklisted`**: The face belongs to a banned individual. The embedding is permanently saved in the database, and they are highlighted in purple across the UI. If detected again, the system will trigger a PLC alarm.
    
- **`rejected`**: Used for false positives, blurry images, or bad data. **Action:** Marking a face as rejected triggers a hard `DELETE FROM persons` query, scrubbing the garbage data entirely from the SQLite database.
    

### 3. UI/UX Architecture Overhaul

The Dashboard templates have been upgraded to provide a native-app experience, bypassing the default Node-RED Dashboard margins and layouts.

- **Immersive Fullscreen:** Both the Registry and the Records Table now utilize `position: fixed` CSS to consume the entire viewport, creating a distraction-free moderation environment.
    
- **Seamless Navigation:** Built-in routing via Vue's `$router.push()` (with fallback to `window.location`) allows instant switching between the Registry and the Table views without reloading the browser.
    
- **Interactive Modals:** The "All Records" table is now fully interactive. Clicking any table row opens a CSS-blurred modal overlay displaying the high-resolution face image linked to that record. We also bound global EventListeners to Vue's lifecycle hooks, allowing users to quickly dismiss the modal by pressing the `ESC` key.
    

### 4. Zero-Touch Deployment & Hypervisor Boot Sequence

We moved the Python backend (`api.py`) directly into the Node-RED project directory. To ensure the system is truly portable and resilient, Node-RED now acts as a hypervisor that provisions its own dependencies on startup using a chained Windows `cmd` command.

**The Boot Sequence:**

1. **PM2 Auto-Provisioning:** The system checks if PM2 exists (`where pm2`). If missing on a new machine, it silently installs it globally via `npm`.
    
2. **Model Pre-fetching:** DeepFace normally downloads its weights (`facenet_weights.h5`) on the first run. We bypass network hiccups by checking the `%USERPROFILE%\.deepface\weights\` directory. If the model is missing, we use native Windows `curl` to fetch it directly from the GitHub releases before Python even starts.
    
3. **Python Dependencies:** It navigates to the project folder, looks for `requirements.txt` (which includes `Flask` and `deepface`), and runs `pip install` to resolve any missing packages.
    
4. **Daemonizing:** Finally, it starts or restarts `api.py` as a PM2 background daemon (`face-api`), ensuring the Flask server is always up and listening on port 5000.
    

### 5. Industrial Protocol Integration (OPC UA & TwinCAT)

We successfully bridged the gap between AI/IT environments and industrial OT environments by connecting the system directly to a Beckhoff PLC via OPC UA.

- **Dynamic Payload Truncation (The Zero-Padding Problem):** PLCs allocate fixed-size memory arrays for buffers (e.g., `ARRAY [0..500000] OF BYTE`). When a smaller `.jpg` is sent, the remaining array is padded with zeros, causing standard Python image libraries to crash. We implemented a custom JS `Function` node that scans the raw byte stream from the PLC, identifies the standard JPEG End-Of-Image (EOI) markers (`FF D9` / `255 217`), and intelligently truncates the garbage padding before HTTP transmission.
    
- **Automated Blacklist Alarming:** We merged the SQLite query and embedding comparison nodes to optimize data fetching. If the Python backend detects a face and the Cosine Distance check matches it to an existing SQLite ID labeled as `blacklisted`, Node-RED immediately constructs a strict, fully-qualified OPC UA Write payload (including `injectType: "write"`, explicit `nodeId`, and data types) to force a `TRUE` value onto the PLC's memory (`ns=4;s=MAIN.stSystem.inputs.iFacialDetec`), triggering physical alarms or automated logic on the factory floor instantly.