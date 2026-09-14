import './index.css';
import { registerRoot } from 'remotion';
import { VideoCompositionRoot } from './Compositions';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <VideoCompositionRoot />
    </>
  );
};

registerRoot(RemotionRoot);
