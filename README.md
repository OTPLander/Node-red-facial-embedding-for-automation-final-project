# Face Registration System

A complete Node-RED flow for managing, storing, and reviewing facial recognition data. This system acts as a bridge between an external Python backend (handling the heavy lifting of embeddings) and a local SQLite database, wrapped in a modern Vue.js dashboard.

## Architecture & Data Flow

1. **Image Reception & Pre-processing:** The system receives a raw image file (simulated via an `Inject` node for testing), extracts the raw byte buffer, and forwards it to an external Python Flask server via HTTP POST.
    
2. **Embedding Generation:** The Python backend calculates the facial embedding and returns it alongside a base64 encoded version of the processed face.
    
3. **Local Storage:** The base64 image is converted back to a binary buffer and saved as a `.jpg` file in a dynamically created local directory (`saved_faces`).
    
4. **Database Logging:** A new record is inserted into a local SQLite database, storing the first name, last name, the absolute path to the saved `.jpg`, the embedding data, and an initial status of `pending`.
    
5. **UI Dashboard:** A Vue.js dashboard fetches all records from the SQLite database. It displays the images by serving them via a local Node-RED HTTP endpoint and allows users to update names and change the recognition status (`pending`, `identified`, `verified`, `rejected`).
    

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
    
- A running instance of the Python embedding server on port 5000.