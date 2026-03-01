"use client";

interface LandingScreenProps {
  onBegin: () => void;
}

export default function LandingScreen({ onBegin }: LandingScreenProps) {
  return (
    <section className="landing-screen">
      <div className="landing-screen__icon" aria-hidden="true">
        <span>✧</span>
      </div>
      <h1 className="landing-screen__title">Meet the future versions of you</h1>
      <p className="landing-screen__subtitle">
        An AI will get to know you through a thoughtful conversation - your values,
        your crossroads, your dreams - then unlock your multiverse.
      </p>
      <button className="button-pill" type="button" onClick={onBegin}>
        Begin Your Journey
      </button>
    </section>
  );
}
