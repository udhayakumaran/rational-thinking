import React from 'react';
import { Series, useVideoConfig } from 'remotion';
import { SceneRenderer } from './components/SceneRenderer';
import type { ScriptData } from './utils/scriptParser';

interface VideoCompositionProps {
  scriptData?: ScriptData;
}

function getGeneratedScript(): ScriptData | null {
  try {
    // Import generated script at render time
    const generated = require('./generated-script.json') as ScriptData;
    return generated;
  } catch {
    return null;
  }
}

export const VideoComposition: React.FC<VideoCompositionProps> = ({ scriptData }) => {
  const { fps } = useVideoConfig();

  const script = scriptData || getGeneratedScript();

  if (!script || !script.scenes || script.scenes.length === 0) {
    return <div>No script data available</div>;
  }

  return (
    <Series>
      {script.scenes.map((scene, index) => {
        const durationSeconds = scene.duration || 5;
        const durationFrames = durationSeconds * fps;

        return (
          <Series.Sequence key={`${scene.type}-${index}`} durationInFrames={durationFrames}>
            <SceneRenderer
              scene={scene}
              startFrame={0}
              duration={durationFrames}
            />
          </Series.Sequence>
        );
      })}
    </Series>
  );
};
