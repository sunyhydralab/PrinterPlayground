<script setup lang="ts">
import { onMounted, ref, toRef, watchEffect, onUnmounted } from 'vue';
import { useGetFile, type Job } from '@/model/jobs';
import * as GCodePreview from 'gcode-preview';

const { getFile } = useGetFile();

const props = defineProps({
  job: Object as () => Job
});

const job = toRef(props, 'job');
const canvas = ref<HTMLCanvasElement | null>(null);
let preview: GCodePreview.WebGLPreview | null = null;
let layers: string[][] = [];
let currentCommandIndex = 0;

onMounted(async () => {
  const gcodeFile = await getFile(props.job!);
  if (!gcodeFile) {
    console.error('Failed to get the file');
    return;
  }

  const fileString = await fileToString(gcodeFile);
  const lines = fileString.split('\n');
  layers = lines.reduce((layers, line) => {
    if (line.startsWith(';LAYER_CHANGE')) {
      layers.push([]);
    }
    if (layers.length > 0) {
      layers[layers.length - 1].push(line as never);
    }
    return layers;
  }, [[]]);

  if (canvas.value) {
    preview = GCodePreview.init({
      canvas: canvas.value,
      extrusionColor: '#808080', // Gray for printed parts
      backgroundColor: 'black',
      buildVolume: { x: 250, y: 210, z: 220 },
    });

    preview.camera.position.set(0, 475, 0);
    preview.camera.lookAt(0, 0, 0);
  }

  watchEffect(() => {
    if (job.value && preview) {
      updateGCodeVisualization();
    }
  });

  // Simulate real-time G-code execution
  simulatePrinting();
});

onUnmounted(() => {
  preview?.processGCode('');
  preview?.clear();
  preview = null;
});

const fileToString = (file: File | undefined) => {
  if (!file) {
    console.error('File is not available');
    return '';
  }

  const reader = new FileReader();
  reader.readAsText(file);
  return new Promise<string>((resolve, reject) => {
    reader.onload = () => {
      resolve(reader.result as string);
    };
    reader.onerror = (error) => {
      reject(error);
    };
  });
};

const updateGCodeVisualization = () => {
  if (!preview) return;

  try {
    const printedGCode = layers.flat().slice(0, currentCommandIndex); // G-code already processed
    const currentGCode = layers.flat()[currentCommandIndex]; // Current G-code command

    preview.clear();
    preview.processGCode(printedGCode);

    if (currentGCode) {
      preview.addGCodeLine(currentGCode, { color: '#00FF00' }); // Bright green for the current position
    }
  } catch (error) {
    console.error('Error updating GCode visualization:', error);
  }
};

const simulatePrinting = () => {
  const interval = setInterval(() => {
    if (currentCommandIndex < layers.flat().length) {
      currentCommandIndex++;
      updateGCodeVisualization();
    } else {
      clearInterval(interval); // Stop simulation when all G-code is processed
    }
  }, 500); // Update every 500ms
};
</script>

<template>
  <canvas ref="canvas"></canvas>
</template>

<style scoped>
canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
