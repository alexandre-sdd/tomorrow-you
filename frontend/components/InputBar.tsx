"use client";

import { FormEvent, useState } from "react";

interface InputBarProps {
  placeholder: string;
  submitLabel?: string;
  disabled?: boolean;
  secondaryActionLabel?: string;
  secondaryActionTitle?: string;
  secondaryActionClassName?: string;
  secondaryActionDisabled?: boolean;
  onSecondaryAction?: () => Promise<void> | void;
  onSecondaryActionPressStart?: () => Promise<void> | void;
  onSecondaryActionPressEnd?: () => Promise<void> | void;
  onSubmit: (text: string) => Promise<void> | void;
}

export function InputBar({
  placeholder,
  submitLabel = "Send",
  disabled,
  secondaryActionLabel,
  secondaryActionTitle,
  secondaryActionClassName,
  secondaryActionDisabled,
  onSecondaryAction,
  onSecondaryActionPressStart,
  onSecondaryActionPressEnd,
  onSubmit,
}: InputBarProps) {
  const [value, setValue] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    await onSubmit(trimmed);
    setValue("");
  };

  return (
    <form className="input-row" onSubmit={handleSubmit}>
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
      />
      {secondaryActionLabel && (onSecondaryAction || onSecondaryActionPressStart || onSecondaryActionPressEnd) ? (
        <button
          type="button"
          className={secondaryActionClassName}
          title={secondaryActionTitle}
          disabled={disabled || secondaryActionDisabled}
          onClick={onSecondaryAction}
          onPointerDown={(event) => {
            if (!onSecondaryActionPressStart) {
              return;
            }
            event.preventDefault();
            event.currentTarget.setPointerCapture(event.pointerId);
            void onSecondaryActionPressStart();
          }}
          onPointerUp={(event) => {
            if (!onSecondaryActionPressEnd) {
              return;
            }
            event.preventDefault();
            void onSecondaryActionPressEnd();
          }}
          onPointerCancel={() => {
            if (!onSecondaryActionPressEnd) {
              return;
            }
            void onSecondaryActionPressEnd();
          }}
          onLostPointerCapture={() => {
            if (!onSecondaryActionPressEnd) {
              return;
            }
            void onSecondaryActionPressEnd();
          }}
          onKeyDown={(event) => {
            if (!onSecondaryActionPressStart) {
              return;
            }
            if (event.key === " " || event.key === "Enter") {
              event.preventDefault();
              void onSecondaryActionPressStart();
            }
          }}
          onKeyUp={(event) => {
            if (!onSecondaryActionPressEnd) {
              return;
            }
            if (event.key === " " || event.key === "Enter") {
              event.preventDefault();
              void onSecondaryActionPressEnd();
            }
          }}
        >
          {secondaryActionLabel}
        </button>
      ) : null}
      <button type="submit" disabled={disabled || !value.trim()}>
        {submitLabel}
      </button>
    </form>
  );
}
