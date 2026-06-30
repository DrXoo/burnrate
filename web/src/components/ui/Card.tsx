import type { PropsWithChildren, ReactNode } from "react";

interface CardProps extends PropsWithChildren {
  title?: string;
  subtitle?: string;
  eyebrow?: string;
  actions?: ReactNode;
  className?: string;
}

export function Card({ title, subtitle, eyebrow, actions, className = "", children }: CardProps) {
  return (
    <section className={`card ${className}`.trim()}>
      {(title || subtitle || actions || eyebrow) && (
        <header className="card-head">
          <div>
            {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
            {title ? <h2>{title}</h2> : null}
            {subtitle ? <p className="card-copy">{subtitle}</p> : null}
          </div>
          {actions ? <div className="card-actions">{actions}</div> : null}
        </header>
      )}
      {children}
    </section>
  );
}
