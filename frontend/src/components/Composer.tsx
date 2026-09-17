import React, { useState, useRef, useEffect } from 'react';
import { 
  Plus, 
  ChevronDown, 
  ArrowLeft, 
  ArrowUp,
  CornerDownLeft, 
  QrCode, 
  Mail, 
  MessageSquare, 
  Link2, 
  Sparkles, 
  Check, 
  X,
  Image as ImageIcon
} from 'lucide-react';
import { AnalysisType } from '../types';

interface ComposerProps {
  selectedModel: AnalysisType;
  onSelectModel: (model: AnalysisType) => void;
  onSubmit: (input: string, explicitModel: AnalysisType, uploadedImage?: string | null, subject?: string | null) => void;
  onOpenQRUpload: () => void;
  uploadedImage: string | null;
  onRemoveUploadedImage: () => void;
  isAnalyzing: boolean;
}

const MODEL_OPTIONS: { id: AnalysisType; label: string; placeholder: string; icon: any }[] = [
  { id: 'auto', label: 'Auto Detect', placeholder: 'Paste or enter something to analyze...', icon: Sparkles },
  { id: 'email', label: 'Email Analysis', placeholder: 'Paste an email to analyze...', icon: Mail },
  { id: 'sms', label: 'SMS Analysis', placeholder: 'Paste a message to analyze...', icon: MessageSquare },
  { id: 'url', label: 'URL Analysis', placeholder: 'Enter a URL to analyze...', icon: Link2 },
  { id: 'qr', label: 'QR Analysis', placeholder: 'Upload a QR code using + or paste payload...', icon: QrCode },
];

export const Composer: React.FC<ComposerProps> = ({
  selectedModel,
  onSelectModel,
  onSubmit,
  onOpenQRUpload,
  uploadedImage,
  onRemoveUploadedImage,
  isAnalyzing,
}) => {
  const [input, setInput] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const attachmentRef = useRef<HTMLDivElement>(null);

  // Auto-resize textarea as user types
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  // Close menus on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setModelDropdownOpen(false);
      }
      if (attachmentRef.current && !attachmentRef.current.contains(e.target as Node)) {
        setAttachmentMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const currentOption = MODEL_OPTIONS.find((m) => m.id === selectedModel) || MODEL_OPTIONS[0];

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleFormSubmit();
    }
  };

  const handleFormSubmit = () => {
    if (isAnalyzing) return;
    if (!input.trim() && !uploadedImage) return;

    const subjectToSend = selectedModel === 'email' ? (emailSubject.trim() || null) : null;
    onSubmit(input.trim(), selectedModel, uploadedImage, subjectToSend);
    setInput('');
    setEmailSubject('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const canSubmit = (input.trim().length > 0 || uploadedImage !== null) && !isAnalyzing;

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-6 pt-2 select-none relative z-20">
      {/* Attached Image Preview Pill if present */}
      {uploadedImage && (
        <div className="mb-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#161715] border border-white/10 text-xs text-[#EDEDE9] animate-in fade-in slide-in-from-bottom-1">
          <QrCode className="w-3.5 h-3.5 text-[#B7D93D]" />
          <span className="font-mono text-[11px] text-[#9E9E98]">
            {uploadedImage.startsWith('data:') ? 'Custom QR Code Image Attached' : 'Sample QR Image Attached'}
          </span>
          <button
            onClick={onRemoveUploadedImage}
            className="text-[#666660] hover:text-[#EDEDE9] p-0.5 rounded-md hover:bg-white/5 transition-colors ml-1"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main Composer Box */}
      <div 
        id="analysis-composer"
        className="relative bg-[#161715] border border-white/10 hover:border-white/15 focus-within:border-[#B7D93D]/40 rounded-2xl p-2.5 transition-all shadow-lg flex flex-col gap-2"
      >
        {/* Attachment & Model Dropdowns relative container */}
        <div className="flex items-end gap-2">
          {/* Left Attachment Button (+) */}
          <div className="relative shrink-0" ref={attachmentRef}>
            <button
              id="composer-attachment-btn"
              type="button"
              onClick={() => {
                setAttachmentMenuOpen(!attachmentMenuOpen);
                setModelDropdownOpen(false);
              }}
              title="Add attachment (QR Code)"
              className={`p-2 rounded-xl text-[#9E9E98] hover:text-[#EDEDE9] hover:bg-white/5 transition-colors flex items-center justify-center ${
                attachmentMenuOpen ? 'bg-white/10 text-[#EDEDE9]' : ''
              }`}
            >
              <Plus className="w-4 h-4 text-[#9E9E98] hover:text-[#EDEDE9]" />
            </button>

            {/* Attachment Menu Popup */}
            {attachmentMenuOpen && (
              <div 
                id="composer-attachment-menu"
                className="absolute bottom-12 left-0 w-56 bg-[#161715] border border-white/10 rounded-xl p-1.5 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100"
              >
                <div className="px-2.5 py-1.5 text-[10px] uppercase font-mono tracking-wider text-[#666660]">
                  Supported Input
                </div>
                <button
                  id="composer-upload-qr-btn"
                  onClick={() => {
                    setAttachmentMenuOpen(false);
                    onOpenQRUpload();
                  }}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs text-[#EDEDE9] hover:bg-white/5 transition-colors text-left"
                >
                  <QrCode className="w-4 h-4 text-[#B7D93D]" />
                  <div>
                    <div className="font-medium">Upload QR Code</div>
                    <div className="text-[10px] text-[#666660]">Image file or screenshot</div>
                  </div>
                </button>
              </div>
            )}
          </div>

          {/* Center Input Area */}
          <div className="flex-1 min-w-0 py-1">
            {/* Email Subject Input (only shown in email mode) */}
            {selectedModel === 'email' && (
              <input
                id="composer-email-subject"
                type="text"
                value={emailSubject}
                onChange={(e) => setEmailSubject(e.target.value)}
                placeholder="Email subject line (optional)..."
                className="w-full bg-transparent text-sm text-[#EDEDE9] placeholder-[#666660] focus:outline-none resize-none leading-relaxed font-sans block border-b border-white/5 pb-2 mb-2"
              />
            )}
            <textarea
              id="composer-textarea"
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedModel === 'email' ? 'Paste email body to analyze...' : currentOption.placeholder}
              className="w-full bg-transparent text-sm text-[#EDEDE9] placeholder-[#666660] focus:outline-none resize-none max-h-44 leading-relaxed font-sans block"
              style={{ minHeight: '24px' }}
            />
          </div>

          {/* Right Controls: Model Dropdown Trigger + Submit Arrow */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Model Dropdown Trigger (Small down arrow / pill) */}
            <div className="relative" ref={dropdownRef}>
              <button
                id="composer-model-dropdown-trigger"
                type="button"
                onClick={() => {
                  setModelDropdownOpen(!modelDropdownOpen);
                  setAttachmentMenuOpen(false);
                }}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-[#9E9E98] hover:text-[#EDEDE9] border border-white/5 transition-colors"
              >
                <span className="text-[11px] font-medium hidden sm:inline">
                  {currentOption.label}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-[#9E9E98]" />
              </button>

              {/* Model Dropdown Menu */}
              {modelDropdownOpen && (
                <div 
                  id="composer-model-menu"
                  className="absolute bottom-12 right-0 w-52 bg-[#161715] border border-white/10 rounded-xl p-1.5 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100"
                >
                  <div className="px-2.5 py-1.5 text-[10px] uppercase font-mono tracking-wider text-[#666660]">
                    Select Analysis Pipeline
                  </div>
                  {MODEL_OPTIONS.map((option) => {
                    const isSelected = selectedModel === option.id;
                    const Icon = option.icon;
                    return (
                      <button
                        key={option.id}
                        id={`model-option-${option.id}`}
                        onClick={() => {
                          onSelectModel(option.id);
                          setModelDropdownOpen(false);
                        }}
                        className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs transition-colors text-left ${
                          isSelected
                            ? 'bg-[#B7D93D]/10 text-[#EDEDE9] font-medium'
                            : 'text-[#9E9E98] hover:bg-white/5 hover:text-[#EDEDE9]'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Icon className={`w-3.5 h-3.5 ${isSelected ? 'text-[#B7D93D]' : 'text-[#9E9E98]'}`} />
                          <span>{option.label}</span>
                        </div>
                        {isSelected && <Check className="w-3.5 h-3.5 text-[#B7D93D]" />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Left Arrow Submit Control */}
            <button
              id="composer-submit-btn"
              type="button"
              disabled={!canSubmit}
              onClick={handleFormSubmit}
              title="Start analysis"
              className={`p-2 rounded-xl transition-all flex items-center justify-center cursor-pointer ${
                canSubmit
                  ? 'bg-[#B7D93D] text-[#0B0C0A] hover:bg-[#C6E74B] shadow-xs active:scale-95'
                  : 'bg-white/5 text-[#666660] cursor-not-allowed'
              }`}
            >
              {isAnalyzing ? (
                <div className="w-4 h-4 border-2 border-[#0B0C0A] border-t-transparent rounded-full animate-spin" />
              ) : (
                /* Left arrow icon representing Enter/Submit as requested in the design spec */
                <CornerDownLeft className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>
      
      {/* Quiet disclaimer */}
      <div className="text-center mt-2 text-[11px] text-[#666660]">
        CyberNexus ML analyzes content indicators locally and via fine-tuned classification models.
      </div>
    </div>
  );
};
