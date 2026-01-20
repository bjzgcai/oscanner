# CLAUDE Project

## Structure
    - evaluator  # evaluator core code, use fastapi
    - webapp     # webapp code, use next + react + antd + antd-x + echarts

## Development Workflow
  - Develop on main branch directly
  - Auto-push triggers PR generation via Gitee workflow
  - Connect PR to issue: use commit message format "fix:  #issue_number"
  - If no issue: use normal commit message

## attention
  remove the temporary files like .md after task done.