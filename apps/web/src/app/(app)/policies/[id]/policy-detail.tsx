"use client";

import Link from "next/link";
import { ArrowLeft, History, Loader2, Save, Stamp, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/brand/error-state";
import { PageHeader } from "@/components/brand/page-header";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import {
  useDeletePolicy,
  usePolicy,
  usePolicyVersions,
  useUpdatePolicy,
} from "@/lib/api/queries";
import type { PolicyOut } from "@/lib/api/types";
import { formatLegalDate } from "@/lib/format";

export const PolicyDetail = ({ policyId }: { policyId: number }) => {
  const router = useRouter();
  const policy = usePolicy(policyId);
  const versions = usePolicyVersions(policyId);
  const deletePolicy = useDeletePolicy();

  if (policy.isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-72 rounded-lg" />
      </div>
    );
  }
  if (policy.isError) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorState error={policy.error} onRetry={() => policy.refetch()} />
      </div>
    );
  }

  const current = policy.data;

  const onDelete = (): void => {
    deletePolicy.mutate(policyId, {
      onSuccess: () => {
        toast.success("Policy retired");
        router.push("/policies");
      },
      onError: (error) =>
        toast.error("Could not retire the policy", {
          description: error instanceof ApiError ? error.message : "Unexpected error.",
        }),
    });
  };

  return (
    <div className="space-y-6">
      <BackLink />

      <PageHeader
        kicker={`Policy · v${current.current_version_no}`}
        title={current.title}
        actions={
          <>
            <Button asChild variant="outline" className="gap-2">
              <Link href="/audits">
                <Stamp className="h-4 w-4" aria-hidden /> Audit this
              </Link>
            </Button>
            <DeleteButton onConfirm={onDelete} pending={deletePolicy.isPending} />
          </>
        }
      />

      <Tabs defaultValue="current">
        <TabsList>
          <TabsTrigger value="current">Current</TabsTrigger>
          <TabsTrigger value="history" className="gap-1.5">
            <History className="h-3.5 w-3.5" aria-hidden />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="current" className="mt-4">
          {/* Re-keyed per version: a fresh editor after every save, no effects. */}
          <PolicyEditor key={current.current_version_no} policy={current} />
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          {versions.isPending ? (
            <Skeleton className="h-40 rounded-lg" />
          ) : versions.isError ? (
            <ErrorState error={versions.error} onRetry={() => versions.refetch()} />
          ) : (
            <ol className="space-y-3">
              {versions.data.items.map((version) => (
                <li
                  key={version.version_no}
                  className="rounded-lg border border-border bg-card p-4 shadow-sheet"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="ledger-label">
                      Version {version.version_no}
                      {version.version_no === current.current_version_no
                        ? " · current"
                        : ""}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatLegalDate(version.created_at)}
                    </span>
                  </div>
                  <p className="line-clamp-4 whitespace-pre-line text-sm text-charcoal-400">
                    {version.body}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

const PolicyEditor = ({ policy }: { policy: PolicyOut }) => {
  const updatePolicy = useUpdatePolicy(policy.id);
  const [title, setTitle] = useState(policy.title);
  const [body, setBody] = useState(policy.body);
  const dirty = title !== policy.title || body !== policy.body;

