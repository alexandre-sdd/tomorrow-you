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
      {secondaryActionLabel && onSecondaryAction ? (
        <button
          type="button"
          className={secondaryActionClassName}
          title={secondaryActionTitle}
          disabled={disabled || secondaryActionDisabled}
          onClick={onSecondaryAction}
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
