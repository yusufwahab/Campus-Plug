import { z } from "zod";

export const phoneSchema = z
  .string()
  .regex(/^(\+234|234|0)\d{10}$/, "Enter a valid Nigerian phone number, like 0803 123 4567");

export const loginSchema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Enter your password") });

export const signupSchema = z.object({
  full_name: z.string().min(2, "Enter your name"),
  email: z.string().email("Enter a valid email"),
  phone: phoneSchema,
  password: z.string().min(8, "Use at least 8 characters"),
});

export const forgotSchema = z.object({ email: z.string().email("Enter a valid email") });

export const resetSchema = z.object({ new_password: z.string().min(8, "Use at least 8 characters") });

export const codeSchema = z.object({ code: z.string().regex(/^\d{6}$/, "Enter the 6-digit code") });

export const profileSchema = z.object({ full_name: z.string().min(2, "Enter your name") });

export const passwordSchema = z.object({
  current_password: z.string().min(1, "Enter your current password"),
  new_password: z.string().min(8, "Use at least 8 characters"),
});
