import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { fadeInSlideUp } from '../../utils/animations';
import { Scene } from '../../utils/scriptParser';

interface QuestionSceneProps {
  scene: Scene;
  startFrame: number;
}

export const QuestionScene: React.FC<QuestionSceneProps> = ({ scene, startFrame }) => {
  const frame = useCurrentFrame();
  const elapsedFrame = frame - startFrame;
  const animationFrame = Math.max(0, elapsedFrame);

  const animationStyle = fadeInSlideUp(animationFrame, 30);

  return (
    <AbsoluteFill
      style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '40px',
      }}
    >
      <div
        style={{
          ...animationStyle,
          textAlign: 'center',
          maxWidth: '90%',
        }}
      >
        <h1
          style={{
            fontSize: 64,
            fontWeight: 700,
            color: '#ffffff',
            margin: '0 0 24px 0',
            lineHeight: 1.2,
          }}
        >
          {scene.title}
        </h1>
        <p
          style={{
            fontSize: 24,
            color: '#e8e8ff',
            margin: 0,
            lineHeight: 1.5,
            fontWeight: 300,
          }}
        >
          {scene.voiceover}
        </p>
      </div>
    </AbsoluteFill>
  );
};
