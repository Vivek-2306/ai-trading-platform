import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50",
  {
    variants: {
      variant: {
        solid: "bg-accent text-white hover:brightness-110",
        glass: "glass hover:bg-white/10",
      },
    },
    defaultVariants: { variant: "glass" },
  },
);

type Props = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button>;

export function Button({ className, variant, ...props }: Props) {
  return <button className={cn(button({ variant }), className)} {...props} />;
}
