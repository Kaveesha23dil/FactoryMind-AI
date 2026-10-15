import AppSidebar from "@/components/layout/AppSidebar";
import DashboardMotion from "@/components/layout/DashboardMotion";
import "@/components/dashboard/overview.css";
import "./shell-theme.css";
import "./dashboard-motion.css";
export default function ShellLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="fm-shell min-h-screen bg-background lg:flex">
      <AppSidebar />
      <main className="min-w-0 flex-1 lg:pl-64"><DashboardMotion>{children}</DashboardMotion></main>
    </div>
  );
}
