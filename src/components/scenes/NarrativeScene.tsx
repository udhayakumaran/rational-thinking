import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Scene } from '../../utils/scriptParser';

interface NarrativeSceneProps {
  scene: Scene;
}

export const NarrativeScene: React.FC<NarrativeSceneProps> = ({ scene }) => {
  return (
    <AbsoluteFill
      style={{
        background: '#f5f5f5',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '40px',
      }}
    >
      <div
        style={{
          textAlign: 'center',
          maxWidth: '90%',
        }}
      >
        <h2
          style={{
            fontSize: 48,
            fontWeight: 600,
            color: '#333333',
            margin: '0 0 24px 0',
            lineHeight: 1.2,
          }}
        >
          {scene.title}
        </h2>
        <p
          style={{
            fontSize: 24,
            color: '#555555',
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
