import type { ComponentProps } from "react";
import * as Primitive from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";
import { Button } from "./button";

export const Dialog = Primitive.Root;
export const DialogTrigger = Primitive.Trigger;
export const DialogTitle = Primitive.Title;
export const DialogDescription = Primitive.Description;

export function DialogContent({ children, className, ...props }: ComponentProps<typeof Primitive.Content>) {
  return <Primitive.Portal>
    <Primitive.Overlay className="fixed inset-0 z-40 bg-slate-950/50" />
    <Primitive.Content {...props} className={cn(
      "fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-3xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl bg-white p-6 shadow-xl focus:outline-none",
      className,
    )}>
      <div className="mb-4 flex justify-end"><Primitive.Close asChild>
        <Button variant="outline">Close evidence</Button>
      </Primitive.Close></div>
      {children}
    </Primitive.Content>
  </Primitive.Portal>;
}
