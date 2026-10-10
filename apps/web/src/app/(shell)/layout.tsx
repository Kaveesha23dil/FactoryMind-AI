import AppSidebar from "@/components/layout/AppSidebar";

export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background lg:flex">
      <AppSidebar />
      <main className="min-w-0 flex-1 lg:pl-64">{children}</main>
    </div>
  );
}