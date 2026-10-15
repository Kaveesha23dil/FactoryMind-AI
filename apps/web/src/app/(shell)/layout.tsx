import AppSidebar from "@/components/layout/AppSidebar";
import DashboardMotion from "@/components/layout/DashboardMotion";
import PreferenceBridge from "@/components/layout/PreferenceBridge";
import "./preferences.css";
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
      <PreferenceBridge />
      <AppSidebar />
      <main className="min-w-0 flex-1 lg:pl-64"><DashboardMotion>{children}</DashboardMotion></main>
    </div>
  );
}
