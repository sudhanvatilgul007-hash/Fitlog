import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
export default function TrendChart({
  days,
  metric,
  unit,
}: {
  days: any[];
  metric: string;
  unit: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={days}>
        <CartesianGrid strokeDasharray="4 4" vertical={false} />
        <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} />
        <YAxis domain={metric === "weightKg" ? ["auto", "auto"] : undefined} />
        <Tooltip formatter={(value: number) => [value, unit]} />
        <Line
          type="monotone"
          dataKey={metric}
          stroke="#647d43"
          strokeWidth={3}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
