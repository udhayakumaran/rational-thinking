import { Composition, CalculateMetadataFunction } from 'remotion';
import { VideoComposition } from './VideoComposition';
import type { ScriptData } from './utils/scriptParser';

const calculateMetadata: CalculateMetadataFunction<{ scriptData: ScriptData }> = ({
  inputProps,
}) => {
  const { scriptData } = inputProps;
  const durationSeconds = scriptData.scenes.reduce((acc, s) => acc + (s.duration || 5), 0);
  return {
    durationInFrames: Math.ceil(durationSeconds * 30),
  };
};

export const VideoCompositionRoot = () => {
  const defaultScript: ScriptData = {
    title: 'Rational Thinking Video',
    topic: 'Default',
    scenes: [
      {
        type: 'question_scene',
        title: 'Loading video...',
        voiceover: 'Please wait while your video is being generated.',
        duration: 3,
      },
    ],
  };

  return (
    <Composition
      id="VideoComp"
      component={VideoComposition}
      durationInFrames={300}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ scriptData: defaultScript }}
      calculateMetadata={calculateMetadata}
    />
  );
};
