export const copy = {
  appTitle: "Chest CT Observatory",
  appKicker: "Educational Volume Explorer",
  disclaimer:
    "This observatory is for educational and technical exploration only. It does not provide clinical diagnosis, medical advice, or treatment planning. All geometric surfaces and candidate marks are unverified algorithmic representations.",
  colorNote:
    "Colors encode educational layers only. They do not represent tissue color, histological staining, or diagnostic look-up tables.",
  coordNote:
    "Coordinates in 3D view are RAS millimeters (X right, Y anterior, Z superior). Native slice coordinates are zero-based voxel indices (i column, j row, k frame).",
  panels: {
    layers: "Geometry Layers",
    clip: "Clip Plane",
    tour: "Guided Tour",
    slice: "Native Slices",
    candidates: "Candidate Marks",
    notes: "Technical Notes",
    stats: "Dataset Statistics",
  },
  accordion: {
    layers: "Geometry Layers",
    clip: "Clip Plane",
    tour: "Guided Tour",
    slice: "Native Slice",
    candidates: "Candidate Marks",
    notes: "Technical Notes",
  },
  layers: {
    visibility: "Layer Visibility",
    opacity: "Layer Opacity",
    missingMesh:
      "No mesh payload is available for this layer. The geometric layer cannot be displayed.",
    meshError:
      "Mesh geometry failed to parse. Geometric surfaces could not be constructed from the payload.",
    loading: "Loading Geometry...",
    educationalColor: "Educational Layer Tint",
  },
  clip: {
    enable: "Enable Clipping",
    axisX: "X Axis (Right)",
    axisY: "Y Axis (Anterior)",
    axisZ: "Z Axis (Superior)",
    position: "Clip Position",
    uncappedWarning:
      "Section clip planes are uncapped. Interior mesh faces remain open and do not represent solid structures or organ caps.",
  },
  slice: {
    axial: "Axial Plane",
    coronal: "Coronal Plane",
    sagittal: "Sagittal Plane",
    index: "Slice Index",
    windowCenter: "Display Window Center",
    windowWidth: "Display Window Width",
    nativeNote:
      "Source slices display native voxel planes. Three-dimensional mesh interpolations do not verify planar slice contents.",
    overlayTitle: "Candidate Overlays",
    crosshair: "Coordinate Crosshair",
    sourceAxisFallback:
      "RAS edge directions are ambiguous. Labels use source voxel axes instead of left/right anatomy.",
  },
  readout: {
    hu: "Voxel Intensity (HU)",
    indices: "Voxel Index (i, j, k)",
    ras: "Position (RAS mm)",
    lps: "Source Position (LPS mm)",
    fractional: "Sub-Voxel Offset",
    outOfBounds:
      "Selected coordinate lies outside volume bounds. No voxel intensity is defined at this location.",
    voxelError:
      "Voxel intensity could not be read from the local volume. Volume data could not be sampled.",
    noSelection: "No Voxel Selected",
  },
  candidates: {
    empty: "No Candidate Marks",
    focus: "Focus Candidate",
    radius: "Candidate Radius (mm)",
    statusPrefix: "Candidate Status:",
    notDiagnosis:
      "All imported marks are algorithmic candidates or unverified candidates. They do not represent clinical findings, nodules, disease, or confirmed diagnoses.",
  },
  tour: {
    start: "Start Tour",
    next: "Next Stop",
    previous: "Previous Stop",
    exit: "Exit Tour",
    empty: "No Tour Stops",
    active: "Tour In Progress",
    fallbackTitles: {
      overview: "Volume Overview",
      lungs: "Lung Surface Geometry",
      airways: "Airway Geometry",
      vascular: "Vascular Candidate Geometry",
      caseCandidate: "Algorithmic Candidate Region",
      sourceEvidence: "Native Slice Comparison",
    },
  },
  stats: {
    loadingManifest: "Loading Dataset Manifest...",
    loadingMeshes: "Loading Layer Meshes...",
    loadingSlice: "Loading Native Slice...",
    ready: "Dataset Ready",
    meshCount: "Loaded Mesh Layers",
    candidateCount: "Algorithmic Candidate Count",
    sliceCount: "Native Slice Count",
    warningsPresent: "Active Geometry Warnings",
  },
  errors: {
    webgl:
      "WebGL context could not be initialized. Hardware-accelerated 3D rendering is unavailable on this device.",
    noManifest:
      "Local API returned an empty response. No dataset manifest was provided by the local server.",
    invalidManifest:
      "Dataset manifest contains an invalid schema. Layer definitions and volume metadata could not be resolved.",
    invalidMesh:
      "Mesh geometry payload failed validation. Surface geometry could not be constructed from the payload.",
    noData:
      "No volumetric data found at the local endpoint. The current session has no layers or slices to display.",
    sliceFailed:
      "Native slice retrieval failed. The requested planar slice could not be loaded from the local API.",
    apiUnreachable:
      "Local same-origin API is unreachable. The local dataset service could not be contacted.",
  },
  a11y: {
    toggleLayer: "Toggle Layer Visibility",
    layerOpacity: "Adjust Layer Opacity",
    sliceAxis: "Select Slice Plane",
    sliceIndex: "Change Slice Index",
    windowCenter: "Adjust Display Window Center",
    windowWidth: "Adjust Display Window Width",
    clipEnable: "Toggle Clip Plane",
    clipPosition: "Adjust Clip Position",
    tourStop: "Select Tour Stop",
    focusCandidate: "Focus Algorithmic Candidate",
    openPanel: "Expand Panel",
    closePanel: "Collapse Panel",
    viewer: "3D Geometry Viewport",
    sliceImage: "Native Slice Viewport",
  },
  buttons: {
    retry: "Retry",
    resetView: "Reset View",
    enableClip: "Enable Clip",
    disableClip: "Disable Clip",
  },
};
