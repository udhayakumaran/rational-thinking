export const fadeInSlideUp = (frame: number, durationInFrames: number) => {
  const progress = Math.min(frame / (durationInFrames * 0.3), 1);
  return {
    opacity: progress,
    transform: `translateY(${(1 - progress) * 30}px)`,
  };
};

export const fadeOut = (frame: number, durationInFrames: number) => {
  const progress = Math.min(frame / (durationInFrames * 0.5), 1);
  return {
    opacity: 1 - progress,
  };
};

export const scaleUp = (frame: number, durationInFrames: number) => {
  const progress = Math.min(frame / (durationInFrames * 0.4), 1);
  return {
    transform: `scale(${0.8 + progress * 0.2})`,
    opacity: progress,
  };
};

export const shipHorizon = (frame: number, durationInFrames: number) => {
  const progress = Math.min(frame / durationInFrames, 1);
  return {
    transform: `translateX(${progress * 100}%) translateY(${progress * -20}px)`,
    opacity: 1 - progress * 0.3,
  };
};

export const starDome = (frame: number, durationInFrames: number) => {
  const progress = Math.min(frame / (durationInFrames * 0.6), 1);
  return {
    transform: `rotate(${progress * 360}deg)`,
    opacity: progress,
  };
};

export const flashlightGlobe = (frame: number, durationInFrames: number) => {
  const progress = Math.min(frame / durationInFrames, 1);
  return {
    filter: `brightness(${0.5 + progress * 0.5})`,
    transform: `scale(${1 + progress * 0.1})`,
  };
};

export const bubbleBurst = (frame: number, durationInFrames: number) => {
  const progress = Math.min(frame / durationInFrames, 1);
  return {
    transform: `scale(${1 + progress * 0.2})`,
    opacity: 1 - progress * 0.3,
  };
};

export const noAnimation = () => ({});