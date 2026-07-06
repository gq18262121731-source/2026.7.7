import type { ReactNode } from "react";

interface InspectionWorkflowLayoutProps {
  children: ReactNode;
  context: ReactNode;
  footer?: ReactNode;
}

export function InspectionWorkflowLayout({ children, context, footer }: InspectionWorkflowLayoutProps) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <main className="min-w-0 space-y-5">
        {children}
        {footer}
      </main>
      {context}
    </div>
  );
}
