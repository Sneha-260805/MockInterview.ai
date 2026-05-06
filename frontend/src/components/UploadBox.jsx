import { useRef, useState } from "react";

const ACCEPT = ".pdf,.txt";

export default function UploadBox({ onFileSelect, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState(null);

  function handleFile(file) {
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "txt"].includes(ext)) {
      alert("Only PDF and TXT files are supported.");
      return;
    }
    setSelected(file);
    onFileSelect(file);
  }

  function onInputChange(e) {
    handleFile(e.target.files[0]);
    e.target.value = "";
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    handleFile(e.dataTransfer.files[0]);
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current.click()}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={`
        relative flex flex-col items-center justify-center gap-3
        border-2 border-dashed rounded-2xl px-8 py-12 cursor-pointer
        transition-colors select-none
        ${disabled ? "opacity-50 cursor-not-allowed border-gray-200 bg-gray-50" : ""}
        ${dragging ? "border-brand-500 bg-brand-50" : "border-gray-300 bg-white hover:border-brand-400 hover:bg-brand-50"}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={onInputChange}
        disabled={disabled}
      />

      <div className="w-14 h-14 rounded-full bg-brand-50 flex items-center justify-center">
        <svg className="w-7 h-7 text-brand-500" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      </div>

      {selected ? (
        <div className="text-center">
          <p className="font-semibold text-gray-800 text-sm">{selected.name}</p>
          <p className="text-xs text-gray-400 mt-0.5">{(selected.size / 1024).toFixed(1)} KB — click to change</p>
        </div>
      ) : (
        <div className="text-center">
          <p className="font-medium text-gray-700 text-sm">
            Drop your resume here, or <span className="text-brand-600 underline underline-offset-2">browse</span>
          </p>
          <p className="text-xs text-gray-400 mt-1">PDF or TXT · max 10 MB</p>
        </div>
      )}
    </div>
  );
}
