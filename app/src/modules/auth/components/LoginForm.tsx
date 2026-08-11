import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface LoginFormProps {
  defaultAccount?: string;
  onSubmit: (account: string, password: string) => Promise<void>;
}

export function LoginForm({
  defaultAccount = "",
  onSubmit,
}: LoginFormProps) {
  const [account, setAccount] = useState(defaultAccount);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await onSubmit(account, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-destructive text-sm">
          {error}
        </p>
      )}
      <div className="space-y-2">
        <Label htmlFor="account">账号</Label>
        <Input
          autoComplete="username"
          id="account"
          onChange={(e) => setAccount(e.target.value)}
          placeholder="请输入账号"
          required
          type="text"
          value={account}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">密码</Label>
        <Input
          autoComplete="current-password"
          id="password"
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          required
          type="password"
          value={password}
        />
      </div>
      <Button className="w-full" disabled={loading} type="submit">
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        登录
      </Button>
    </form>
  );
}
