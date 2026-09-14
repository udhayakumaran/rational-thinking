export interface Scene {
  type: 'question_scene' | 'narrative_scene' | 'experiment_scene' | 'interactive_scene' | 'reflection_scene';
  title: string;
  voiceover: string;
  duration?: number;
  description?: string;
}

export interface ScriptData {
  title: string;
  topic: string;
  scenes: Scene[];
}

export const parseScript = (jsonString: string): ScriptData => {
  return JSON.parse(jsonString);
};

export const getSceneFrameCount = (scene: Scene, fps: number): number => {
  return Math.round((scene.duration || 5) * fps);
};