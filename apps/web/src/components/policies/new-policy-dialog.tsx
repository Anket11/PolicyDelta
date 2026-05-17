"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { FilePlus2, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import { useCreatePolicy } from "@/lib/api/queries";
import { MAX_POLICY_BODY_CHARS } from "@/lib/constants";

const formSchema = z.object({
  title: z.string().min(1, "Give the policy a title.").max(300),
  body: z.string().min(1, "Policy text is required.").max(MAX_POLICY_BODY_CHARS),
});

type FormValues = z.infer<typeof formSchema>;

export const NewPolicyDialog = () => {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const createPolicy = useCreatePolicy();

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { title: "", body: "" },
  });

  const onSubmit = (values: FormValues): void => {
    createPolicy.mutate(values, {
      onSuccess: (policy) => {
        toast.success("Policy stored", { description: `${policy.title} · v1` });
        setOpen(false);
        form.reset();
        router.push(`/policies/${policy.id}`);
      },
      onError: (error) =>
        toast.error("Could not store the policy", {
          description: error instanceof ApiError ? error.message : "Unexpected error.",
        }),
    });
  };

