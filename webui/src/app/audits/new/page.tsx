"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FileUp, Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") {
        const idx = result.indexOf(",");
        resolve(idx >= 0 ? result.slice(idx + 1) : result);
      } else {
        reject(new Error("Failed to read file"));
      }
    };
    reader.onerror = () => reject(reader.error || new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

function textToBase64(text: string): string {
  if (typeof window === "undefined") return "";
  return window.btoa(unescape(encodeURIComponent(text)));
}

export default function NewAuditPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [pastedText, setPastedText] = useState("");
  const [parties, setParties] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [contractType, setContractType] = useState("");
  const [requester, setRequester] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      let document_b64 = "";
      let filename = "pasted-clauses.txt";
      if (file) {
        document_b64 = await fileToBase64(file);
        filename = file.name;
      } else if (pastedText.trim()) {
        document_b64 = textToBase64(pastedText);
      } else {
        throw new Error("Provide a PDF upload or pasted contract text.");
      }
      const partiesArr = parties
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
      const res = await api.createAudit({
        filename,
        document_b64,
        parties: partiesArr,
        jurisdiction: jurisdiction || undefined,
        contract_type: contractType || undefined,
        requester: requester || undefined,
      });
      router.push(`/audits/${res.audit_id}`);
    } catch (err: any) {
      setError(err?.message || "Failed to start audit");
      setBusy(false);
    }
  };

  return (
    <div className="container max-w-3xl space-y-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">New audit</h1>
        <p className="text-sm text-muted-foreground">
          Upload a contract PDF (or paste raw clauses) to run the Compliance 360 pipeline.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Contract intake</CardTitle>
          <CardDescription>
            We will run input guardrails, extract clauses, retrieve matching
            GDPR / ISO / Local Law regulations, and produce a risk-scored audit.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="parties">Parties (comma-separated)</Label>
                <Input
                  id="parties"
                  placeholder="Acme Corp, Beta Ltd"
                  value={parties}
                  onChange={(e) => setParties(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="jurisdiction">Jurisdiction</Label>
                <Input
                  id="jurisdiction"
                  placeholder="EU / Israel / California"
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contract_type">Contract type</Label>
                <Input
                  id="contract_type"
                  placeholder="MSA, DPA, NDA, Employment, ..."
                  value={contractType}
                  onChange={(e) => setContractType(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="requester">Requester</Label>
                <Input
                  id="requester"
                  placeholder="Your name"
                  value={requester}
                  onChange={(e) => setRequester(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="file">Contract PDF</Label>
              <div className="flex items-center gap-3">
                <Input
                  id="file"
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
                {file && (
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <FileUp className="h-3 w-3" /> {file.name}
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="paste">…or paste raw clauses</Label>
              <Textarea
                id="paste"
                rows={8}
                placeholder="1. Definitions ...\n2. Data Processing ...\n3. Liability ..."
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Useful for demos without a PDF. The doc-analyzer accepts both.
              </p>
            </div>

            {error && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <Button type="submit" disabled={busy}>
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Running Compliance 360 ...
                  </>
                ) : (
                  "Run audit"
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
