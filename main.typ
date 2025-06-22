#import "template_ifc_cost_schedule.typ": *
#show: project.with(
  schedule_path: "schedule.csv",
  title: "Casa ZP",
  schedule_name: "Computo di progetto",
  schedule_type: "SCHEDULEOFRATES",
  cover_page: false,
  root_items_to_new_page: false,
  summary: true,
)
