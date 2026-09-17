import React from 'react';
import { ArrowRight, Shield, Sparkles } from 'lucide-react';

interface LandingPageProps {
  onGetStarted: () => void;
  onSignIn: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onGetStarted, onSignIn }) => {
  return (
    <div id="landing-page" className="min-h-screen bg-[#0B0C0A] text-[#EDEDE9] flex flex-col justify-between selection:bg-[#B7D93D]/20 selection:text-[#B7D93D]">
      {/* Header */}
      <header className="w-full max-w-5xl mx-auto px-6 py-8 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-[#B7D93D]" />
          <span className="font-semibold text-lg tracking-tight text-[#EDEDE9]">
            CyberNexus
          </span>
        </div>

        <nav className="flex items-center gap-6 text-sm">
          <button
            id="landing-signin-btn"
            onClick={onSignIn}
            className="text-[#9E9E98] hover:text-[#EDEDE9] transition-colors font-medium px-2 py-1"
          >
            Sign In
          </button>
          <button
            id="landing-getstarted-btn"
            onClick={onGetStarted}
            className="bg-[#B7D93D] text-[#0B0C0A] hover:bg-[#C6E74B] transition-colors font-medium px-4 py-2 rounded-lg text-sm"
          >
            Get Started
          </button>
        </nav>
      </header>

      {/* Hero Section */}
      <main className="w-full max-w-3xl mx-auto px-6 py-16 my-auto flex flex-col items-center text-center">
        <div className="mb-4 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#161715] border border-white/5 text-xs text-[#9E9E98]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#B7D93D]" />
          CyberNexus Analysis Engine v2.4
        </div>

        <h1 className="text-4xl sm:text-5xl md:text-6xl font-medium tracking-tight text-[#EDEDE9] mb-6 leading-[1.15]">
          Check before you trust.
        </h1>

        <p className="text-lg sm:text-xl text-[#9E9E98] max-w-xl font-normal leading-relaxed mb-10">
          Analyze emails, messages, links and QR codes with machine-learning based detection.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4 mb-16">
          <button
            id="hero-get-started-cta"
            onClick={onGetStarted}
            className="w-full sm:w-auto bg-[#B7D93D] text-[#0B0C0A] hover:bg-[#C6E74B] active:scale-[0.99] transition-all font-medium px-7 py-3.5 rounded-xl text-base flex items-center justify-center gap-2 shadow-sm"
          >
            Get Started
            <ArrowRight className="w-4 h-4 text-[#0B0C0A]" />
          </button>

          <button
            id="hero-signin-link"
            onClick={onSignIn}
            className="w-full sm:w-auto text-[#9E9E98] hover:text-[#EDEDE9] transition-colors font-medium px-5 py-3.5 text-base"
          >
            Sign In
          </button>
        </div>

        {/* Restrained Scope Subtitle */}
        <div className="text-xs sm:text-sm text-[#666660] tracking-widest font-mono uppercase">
          Email · SMS · URL · QR
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full max-w-5xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between text-xs text-[#666660] border-t border-white/5 gap-4">
        <div>
          Machine Learning Final Year Project Prototype
        </div>
        <div className="flex items-center gap-6">
          <span>Ensemble Transformer & GBDT Architecture</span>
          <span>Zero Logging Privacy</span>
        </div>
      </footer>
    </div>
  );
};
