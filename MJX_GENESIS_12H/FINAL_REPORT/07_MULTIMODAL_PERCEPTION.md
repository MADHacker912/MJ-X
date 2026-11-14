# MJ-X GENESIS FINAL REPORT — 07: MULTIMODAL PERCEPTION

**Subsystem:** Vision Perception, Coordinate Normalization & Visual Grounding  
**Package:** `mjx.agent.computer_vision`, `actions.screen_processor`  

---

## 1. VISION CAPTURE PIPELINE

MJ-X integrates real-time visual perception across two primary modalities:
1. **Screen Capture:** High-efficiency frame grabbing with resolution downsampling to 1080p, encoded into JPEG/PNG bytes for Gemini Live or local OCR inspection.
2. **Webcam Capture:** Camera frame capture gated by explicit user permission grants.

---

## 2. 1000-POINT NORMALIZED COORDINATE SYSTEM

To prevent fragile coordinate hardcoding across different monitors and DPI scalings, `DesktopPerception` normalizes all screen positions:
- **Normalized Space:** $(0, 0)$ at top-left to $(1000, 1000)$ at bottom-right.
- **Dynamic Transformation:**
  $$\text{Pixel}_X = \frac{\text{Norm}_X \cdot \text{Screen Width}}{1000}, \quad \text{Pixel}_Y = \frac{\text{Norm}_Y \cdot \text{Screen Height}}{1000}$$
- Fully reversible mapping allows UI models to output scale-independent bounding boxes.

---

## 3. UI ELEMENT LOCALIZATION & TARGETING

- Bounding box abstraction (`UIElementBox`) stores label, confidence, and normalized bounds.
- Exact and fuzzy substring query matching finds buttons, search inputs, and navigation elements reliably without requiring full computer vision recalculation for every frame.
