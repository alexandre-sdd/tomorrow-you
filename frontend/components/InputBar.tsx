import { FormEvent, useState } from "react";

interface InputBarProps {
  placeholder: string;
  submitLabel: string;
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export default function InputBar({ placeholder, submitLabel, onSubmit, disabled }: InputBarProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = value.trim();
    if (!text || disabled) {
      return;
    }
    onSubmit(text);
    setValue("");
  }

  return (
    <form className="input-bar" onSubmit={handleSubmit}>
      <input
        className="input-bar__field"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
      />
      <button className="input-bar__button" type="submit" disabled={disabled || !value.trim()}>
        {submitLabel}
      </button>
    </form>
  );
}
