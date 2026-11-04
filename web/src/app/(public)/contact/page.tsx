"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { FormError } from "@/components/auth/AuthCard";
import { ProsePage } from "@/components/layout/Prose";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { ApiError, api } from "@/lib/api";

const schema = z.object({
  name: z.string().min(2, "Enter your name"),
  email: z.string().email("Enter a valid email"),
  topic: z.enum(["order", "payment", "account", "report", "other"]),
  message: z.string().min(10, "Tell us a little more (at least 10 characters)"),
});
type Values = z.infer<typeof schema>;

export default function ContactPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { topic: "other" } });
  const errors = form.formState.errors;

  async function onSubmit(values: Values) {
    setError(null);
    try {
      await api("/contact", { method: "POST", body: values, token: null });
      setSent(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send your message.");
    }
  }

  return (
    <ProsePage title="Contact us" intro="Tell us what happened and we will reply by email.">
      {sent ? (
        <p role="status" className="rounded-card bg-verified-bg p-5 font-semibold text-verified-fg">
          Thanks, your message is with our team. We reply by email.
        </p>
      ) : (
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 rounded-card border border-line bg-white p-5" noValidate>
          <Input label="Your name" error={errors.name?.message} {...form.register("name")} />
          <Input label="Email" type="email" error={errors.email?.message} {...form.register("email")} />
          <Select label="Topic" {...form.register("topic")}>
            <option value="order">An order</option>
            <option value="payment">A payment</option>
            <option value="account">My account</option>
            <option value="report">Report someone</option>
            <option value="other">Something else</option>
          </Select>
          <Textarea label="Message" error={errors.message?.message} {...form.register("message")} />
          <FormError message={error} />
          <Button type="submit" loading={form.formState.isSubmitting}>
            Send message
          </Button>
        </form>
      )}
    </ProsePage>
  );
}
