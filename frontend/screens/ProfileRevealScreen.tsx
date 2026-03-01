"use client";

import { useRef, useState } from "react";
import { ProfileCard } from "@/components/ProfileCard";
import { ScreenHeader } from "@/components/ScreenHeader";
import { uploadUserPhoto } from "@/lib/api";
import type { SelfCard, UserProfile } from "@/lib/types";

interface ProfileRevealScreenProps {
  sessionId: string;
  profile: UserProfile;
  currentSelf: SelfCard;
  onContinue: () => void;
}

export function ProfileRevealScreen({
  sessionId,
  profile,
  currentSelf,
  onContinue,
}: ProfileRevealScreenProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle");

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Show local preview immediately
    const objectUrl = URL.createObjectURL(file);
    setPreview(objectUrl);
    setUploadState("uploading");

    try {
      await uploadUserPhoto(sessionId, file);
      setUploadState("done");
    } catch {
      setUploadState("error");
    }
  }

  return (
    <section className="stack-screen">
      <ScreenHeader
        eyebrow="Onboarding complete"
        title="Your current self is ready"
        subtitle="This profile snapshot will anchor future branching and conversations."
      />

      <ProfileCard profile={profile} />

      <article className="surface-card current-self-card">
        <h3>{currentSelf.name}</h3>
        <p>{currentSelf.optimizationGoal}</p>
      </article>

      {/* Optional reference photo upload */}
      <div className="photo-upload-section">
        <p className="photo-upload-label">
          Add a photo of yourself — future selves will be generated with your likeness.
        </p>

        <div className="photo-upload-row">
          {preview ? (
            <img src={preview} alt="Your reference photo" className="photo-preview" />
          ) : (
            <div className="photo-preview-placeholder" aria-hidden="true">
              <span>?</span>
            </div>
          )}

          <div className="photo-upload-controls">
            <button
              type="button"
              className="ghost-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadState === "uploading"}
            >
              {preview ? "Change photo" : "Upload photo"}
            </button>

            {uploadState === "uploading" && (
              <span className="photo-status">Uploading…</span>
            )}
            {uploadState === "done" && (
              <span className="photo-status photo-status-ok">Saved</span>
            )}
            {uploadState === "error" && (
              <span className="photo-status photo-status-err">Upload failed — you can continue without it.</span>
            )}
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="visually-hidden"
          onChange={handleFileChange}
        />
      </div>

      <button type="button" onClick={onContinue} className="primary-cta">
        View future selves
      </button>
    </section>
  );
}
