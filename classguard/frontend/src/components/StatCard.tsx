interface Props {
  label: string
  value: number | string
  color: string
}

export function StatCard({ label, value, color }: Props) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-600">{label}</span>
        <span className={`text-2xl font-bold ${color}`}>{value}</span>
      </div>
    </div>
  )
}
