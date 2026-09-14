import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { scaleUp } from '../../utils/animations';
import { Scene } from '../../utils/scriptParser';

interface InteractiveSceneProps {
  scene: Scene;
  startFrame: number;
}

export const InteractiveScene: React.FC<InteractiveSceneProps> = ({ scene, startFrame }) => {
  const frame = useCurrentFrame();
  const elapsedFrame = frame - startFrame;
  const animationFrame = Math.max(0, elapsedFrame);

  const animationStyle = scaleUp(animationFrame, 30);

  return (
    <AbsoluteFill
      style={{
        background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
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
            color: '#ffe0e8',
            margin: '0 0 32px 0',
            lineHeight: 1.6,
            fontWeight: 400,
          }}
        >
          {scene.voiceover}
        </p>
        <div
          style={{
            fontSize: 18,
            color: '#ffffff',
            backgroundColor: 'rgba(255, 255, 255, 0.2)',
            padding: '16px 24px',
            borderRadius: '8px',
            display: 'inline-block',
            lineHeight: 1.5,
          }}
        >
          Try it yourself!
        </div>
      </div>
    </AbsoluteFill>
  );
};
