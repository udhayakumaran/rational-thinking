import React from 'react';
import { Scene } from '../utils/scriptParser';
import { QuestionScene } from './scenes/QuestionScene';
import { NarrativeScene } from './scenes/NarrativeScene';
import { ExperimentScene } from './scenes/ExperimentScene';
import { InteractiveScene } from './scenes/InteractiveScene';
import { ReflectionScene } from './scenes/ReflectionScene';

interface SceneRendererProps {
  scene: Scene;
  startFrame: number;
  duration: number;
}

export const SceneRenderer: React.FC<SceneRendererProps> = ({ scene, startFrame, duration }) => {
  switch (scene.type) {
    case 'question_scene':
      return <QuestionScene scene={scene} startFrame={startFrame} />;

    case 'narrative_scene':
      return <NarrativeScene scene={scene} />;

    case 'experiment_scene':
      return <ExperimentScene scene={scene} startFrame={startFrame} />;

    case 'interactive_scene':
      return <InteractiveScene scene={scene} startFrame={startFrame} />;

    case 'reflection_scene':
      return <ReflectionScene scene={scene} startFrame={startFrame} duration={duration} />;

    default: {
      const _exhaustive: never = scene.type;
      return _exhaustive;
    }
  }
};
