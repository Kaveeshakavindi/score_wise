// Shared shell + field styling for the /login and /register screens, kept
// visually consistent with the rest of the design system (rounded-3xl card,
// shadow-soft, coral-accented focus states) without duplicating markup
// across the two pages.

export const AUTH_SUBMIT =
  "rounded-full bg-coral px-6 py-3.5 text-base font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02]";

const INPUT =
  "w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-text-dark placeholder:text-stone-400 outline-none transition-colors focus:border-coral-dark";

export function AuthCard({
  icon,
  eyebrow,
  title,
  subtitle,
  children,
}: {
  icon: React.ReactNode;
  eyebrow: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative z-10 w-full max-w-md animate-reveal rounded-3xl border border-stone-100 bg-white p-8 shadow-soft sm:p-10">
      <div className="mb-8 flex flex-col items-center gap-3 text-center">
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-coral text-text-dark">
          {icon}
        </span>
        <p className="text-sm font-medium tracking-wide text-coral-dark">{eyebrow}</p>
        <h1 className="text-3xl font-medium text-text-dark">{title}</h1>
        <p className="text-sm text-text-muted">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

type AuthFieldProps = {
  label: string;
  type: "text" | "email" | "password" | "number";
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  pattern?: string;
  title?: string;
  minLength?: number;
  min?: number;
  max?: number;
};

export function AuthField({ label, value, onChange, ...inputProps }: AuthFieldProps) {
  const id = `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-text-dark">
        {label}
      </label>
      <input
        id={id}
        className={INPUT}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        {...inputProps}
      />
    </div>
  );
}
