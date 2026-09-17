import React, { useState, useRef } from 'react';
import { X, Upload, QrCode, ArrowRight, ShieldAlert, Sparkles, Check } from 'lucide-react';

interface QRUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectQR: (imageData: string, label: string) => void;
}

const SAMPLE_QRS = [
  {
    id: 'sample-parking',
    name: 'Parking Meter Overlay',
    description: 'Physical payment QR code sticker simulating meter payment gateway',
    category: 'PARKING',
    imageData: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAUgAAAFIAQAAAAAab1qeAAAClUlEQVR4nO1a7Y4bIQy0rbz/K09lewzb/mIrteAc6O5CwLqYyfhzUcjisFVBuZIrw5akfrrkR0RzBoVCxH9FBSrwl7Hb5kS2VfITWAWEogmiv01QHWOp3S4nsv2SqslCDTQ1sU0g5+4BejbhJwdEA83ENP0A+p3oGEmltQOOqwRB9UA9z+cnYkpWQuFoRkjieqsT2XY8NacZ3QvTiPexLCfoaU0k9bd83oGk28yU6bFt/+DT7esklSHdR0EZ65kyOaDq6zf/fOE/9RndI++kN/WYpC6B3d+7NZFUmvaoh2ZI5xwM+11OZFslBfBwnlSMWXAzpnNBBOhyIjtAEknFQUc60cpCgUP0bJEvKWv2LNczX2Lhrg6lplfociLbKikIQ88p34SRlxcQ7l17f1Ef6WjXxSSzUPaYlHVSF4bYGfWRZmVUaShBLqhlt57WSRIVz5l9htl7GU+WnqJnD0kwe0d1Qf3HjT4Iq8Xb7Xp2iUeY5GSuObPQQV7ceLQ0NJmZKVO0Q6oN8mfDztb+oVxJuKlD07QrBx0BCQxYF8+VoRWEskh6dusmrvCa6eL5tv+ps1nHAPVs4pmsDvvBkh//E2aepSW9pz9LStJq8na3ntZEUisSVaOO1xnyYXwSFDefl1f1EUhDf2F7qTokw522YYid0Q8B00x2RZ49EcRalxPZAZL6uKuU5RFnY0GO0LNFPALpGc/dR7eJRl8PPXbraf3u18l8XpxhqmZynx/JCzxlpvTjRl3dZKpN7P7erVv+KfOCSDVAhyMVR7nLiewoSfh1MI/ohDLe/7dP/ypJFIp5HYxGj3Kkx+h5vr0j515yZsuO8X64Vt2upzW8XyfZmOed70ecx+3P/939um9giF3JhdEFpV+ca1ZXkqxRqgAAAABJRU5ErkJggg=='
  },
  {
    id: 'sample-crypto',
    name: 'Crypto AirDrop Giveaway',
    description: 'Promotional giveaway QR code claiming USDT token distribution',
    category: 'CRYPTO',
    imageData: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASgAAAEoAQAAAADDfFG0AAACJElEQVR4nO1Zy3LDMAhkmfz/L9NhAclpk7iH1CJT4cSRLQ7MhseCYPIL0d8oydYq2UgMsXIw88v8Nx9iRZWNV8mN4IgIRGAInHwBOexsvEqIBODo0KMKrsKKOxuvO/9KoU/xm6jNre1fD5CwTF1+B4jcA60X8m/8y2JN14rFLAKL7NLPqI9yf5VKV+v1ci3MLAVLx+L9mL7aWq9L/Msi7px+xVO893Vsbv8aooETGJfFKgggipQ1/rd1hRby4yUx7o6Yr0bmb2z9gvoIRh3TV8JmyDJgoIN1tV4v17o5JiBc4VnEJ1yO/rbILm2qhWRcNgtiZDE2RVUyu1qvS7QAROaC8/pgE9wcPXdn68/l3VrmGctvXhrZajOVMUDR3vpzebt/Cf2LfsWySJACKWtv/bm8na9acNWEp+Y6tdx89Xt9tJHloyYm5S8y1vff1iVa5gSsJhMkYx6dzGbZj3e2/lz+pN/GeEUOUe8jrXW1XldogVn+kMRqVkE3Y9lsbP0Cfi9kpzm393U025nv0dh6XdQ/gjjV9L7Y6pxYdLVeL9eSiEPhcg5ZD7NVD9Ku1uuqeLS7qf04tBW24n2t18u1bqMy2iGJpTBMN594dr4tpKdVE9PBdv76eZ6GWQkZmJN7pb91jQ5dqYUYp44zbh547PnEc1StTmyZtmrGuvnEUcZgFdV0HxJaNNs7Hl+cb0ueOE4W5nH5Adnk6n77I63XrZXSFYkvzaYe9g8aPn8AAAAASUVORK5CYII='
  },
  {
    id: 'sample-safe',
    name: 'Guest Wi-Fi Access',
    description: 'Standard enterprise WPA2/WPA3 configuration token',
    category: 'WI-FI',
    imageData: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASgAAAEoAQAAAADDfFG0AAACEElEQVR4nO1ZXXPCQAiEG///X94On5eksfrg3OEU1JrmeGBWWBbCoDdsvONE7RXWSIQ9iNiuQExgkL3ln3nSeIU9FA8SfAQhCGZyQyDLk8brhJcgIsh4VoEttzBPOr/CjkhwVCWuTaDxukECVomZVXzr9Yf9m3qEXTtnMYTxje1RO/qx3Iuy9nDzCpeq0Y/lXjypijOdridlox9b9BfkgiWfBDItQ8XOJRjqRj+We3FILBhEjpIIV884uaoa/djhxZ5MKrzUDC7TrVw8+vVesLZomaSd0XILnBRWOPr1/RGC0Lkj+olCKX+rRj/2eLHxmHwUM0OKdaTUG6WjX873bD3RGcvZf06QjdeveRvJ70Zguczh2r/22LT/Yuf31PvRMl2PVY1+bPGCqyxnfFcVhqEVa+XoX9uH8wvOVspazmRzPYHK0Y/lXuTqi6I32g2XFq0nrpbbesJJ1lti6Xa69/eXLFRITNsnWkJj8sWlq2Ns8QKnBGOfJrMg7VM5+tf2cS/oMkcr0pR9DEYKV/fHoxmlkwMWd3J1qONlz4+3+1Uk/wfPx3Hp6ti1v8dxk3/ksM6v2+fb5IJ1LnYEM82wqr/22OPFNgJJmzyNQrLRUeVfOvptXjDWkrUq6/AtzbL30U/xYhFisZIILdH7iafPt6HsFao+nhw1f53s2hWR74ME+wY2Wf58+wujH+3lVhWJH1Z8GfCp2J+wAAAAAElFTkSuQmCC'
  }
];

export const QRUploadModal: React.FC<QRUploadModalProps> = ({
  isOpen,
  onClose,
  onSelectQR,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      onSelectQR(dataUrl, file.name);
      onClose();
    };
    reader.readAsDataURL(file);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        id="qr-upload-modal"
        className="w-full max-w-lg bg-[#10110F] border border-white/10 rounded-2xl p-6 sm:p-7 shadow-2xl relative space-y-5"
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-[#9E9E98] hover:text-[#EDEDE9] p-1.5 rounded-lg hover:bg-white/5 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-[#161715] border border-white/5">
            <QrCode className="w-5 h-5 text-[#B7D93D]" />
          </div>
          <div>
            <h3 className="text-lg font-medium text-[#EDEDE9] tracking-tight">
              Upload QR Code Image
            </h3>
            <p className="text-xs text-[#9E9E98]">
              Decodes QR optical matrix and passes payload to ML threat models.
            </p>
          </div>
        </div>

        {/* Drag & drop zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3 ${
            dragActive
              ? 'border-[#B7D93D] bg-[#B7D93D]/5'
              : 'border-white/10 hover:border-white/20 bg-[#161715]/60'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFile(e.target.files[0]);
              }
            }}
          />
          <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center text-[#B7D93D]">
            <Upload className="w-5 h-5" />
          </div>
          <div>
            <span className="text-sm font-medium text-[#EDEDE9] block">
              Drag & drop QR image or click to browse
            </span>
            <span className="text-xs text-[#666660] mt-1 block">
              PNG, JPG, WEBP, or SVG screenshot
            </span>
          </div>
        </div>

        {/* Preset Sample QR Scenarios */}
        <div className="space-y-2.5 pt-2">
          <div className="text-[11px] font-mono uppercase tracking-wider text-[#666660]">
            Or choose a preset sample QR to test:
          </div>
          <div className="space-y-2">
            {SAMPLE_QRS.map((sample) => (
              <button
                key={sample.id}
                onClick={() => {
                  onSelectQR(sample.imageData, sample.name);
                  onClose();
                }}
                className="w-full flex items-center justify-between p-3 rounded-xl bg-[#161715] hover:bg-[#1C1E1A] border border-white/5 hover:border-[#B7D93D]/30 transition-all text-left group"
              >
                <div className="space-y-0.5 min-w-0 pr-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-[#EDEDE9] group-hover:text-[#B7D93D] transition-colors">
                      {sample.name}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded text-[#9E9E98] bg-white/5 border border-white/5">
                      {sample.category}
                    </span>
                  </div>
                  <div className="text-[11px] text-[#9E9E98] truncate">
                    {sample.description}
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-[#666660] group-hover:text-[#B7D93D] group-hover:translate-x-0.5 transition-all shrink-0" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
