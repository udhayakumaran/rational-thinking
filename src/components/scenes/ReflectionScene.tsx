import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { fadeOut } from '../../utils/animations';
import { Scene } from '../../utils/scriptParser';

interface ReflectionSceneProps {
  scene: Scene;
  startFrame: number;
  duration: number;
}

export const ReflectionScene: React.FC<ReflectionSceneProps> = ({ scene, startFrame, duration }) => {
  const frame = useCurrentFrame();
  const elapsedFrame = frame - startFrame;
  const animationFrame = Math.max(0, elapsedFrame);

  const animationStyle = fadeOut(animationFrame, duration);

  return (
    <AbsoluteFill
      style={{
        background: 'linear-gradient(135deg, #4a148c 0%, #880e4f 100%)',
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
        <h2
          style={{
            fontSize: 48,
            fontWeight: 600,
            color: '#ffffff',
            margin: '0 0 24px 0',
            lineHeight: 1.2,
          }}
        >
          {scene.title}
        </h2>
        <p
          style={{
            fontSize: 24,
            color: '#f0e6ff',
            margin: 0,
            lineHeight: 1.6,
            fontWeight: 400,
          }}
        >
          {scene.voiceover}
        </p>
      </div>
    </AbsoluteFill>
  );
};
