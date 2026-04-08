export function isImportableGpu(gpu) {
  return gpu?.available !== false
}

export function selectableGpuIndexes(gpus = []) {
  return gpus
    .filter((gpu) => isImportableGpu(gpu))
    .map((gpu) => Number(gpu.index))
}
