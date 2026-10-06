# IntelliCRM --- DESIGN.md

## 1. Purpose

This document is the authoritative UI/UX specification for IntelliCRM.

The implementation must reproduce the approved visual direction shown in
the reference dashboard image: - Professional enterprise B2B SaaS CRM -
Light main workspace - Dark navy left sidebar - White cards with
restrained borders/shadows - Blue as the primary action/accent color -
Green/amber/red only for meaningful status states - Dense but readable
business information - Minimal decoration - No "AI-looking" visual
effects

Do not redesign the product into a generic AI dashboard.

------------------------------------------------------------------------

## 2. Design Principles

### 2.1 Visual principles

1.  Clean enterprise SaaS appearance.
2.  Information density should feel appropriate for a real CRM.
3.  Use whitespace for hierarchy, not oversized empty areas.
4.  Use cards only when they improve grouping.
5.  Prefer tables, timelines, lists, charts, badges, and structured
    panels.
6.  AI must be contextual and subtle.
7.  No excessive gradients.
8.  No glassmorphism.
9.  No neon glow.
10. No giant robot/brain imagery.
11. No purple AI theme.
12. No excessive rounded "pill" containers.
13. Do not make every element a floating card.

### 2.2 Typography

Preferred: - Inter, Geist, or IBM Plex Sans - Body: 13--14px - Secondary
text: 12--13px - Section heading: 18--20px - Page title: 24--28px - KPI
number: 24--30px - Table text: 13px

Font weights: - 400 normal - 500 labels - 600 headings - 700 only for
important KPI numbers

### 2.3 Color system

Use CSS variables/tokens. Do not hard-code colors throughout components.

``` css
--bg: #F5F7FA;
--surface: #FFFFFF;
--surface-muted: #F8FAFC;
--sidebar: #111827;
--sidebar-hover: #1F2937;
--text: #111827;
--text-secondary: #64748B;
--border: #E5E7EB;
--primary: #2563EB;
--primary-hover: #1D4ED8;
--success: #16A34A;
--warning: #D97706;
--danger: #DC2626;
--info: #0EA5E9;
```

These are defaults. Keep the system visually restrained.

### 2.4 Radius and shadows

Default radius: - Small controls: 6px - Inputs/buttons: 7--8px - Cards:
10--12px - Modal: 12px

Avoid very round 20--30px cards.

Use subtle shadows: - `0 1px 2px rgba(15,23,42,0.05)` - Slightly
stronger shadow only for modal/dropdown.

------------------------------------------------------------------------

## 3. Global Application Layout

Desktop target: - 1440px × 900px reference - Sidebar: 240--256px - Main
content: remaining width - Top header: 64px - Main content padding:
24--32px

Structure:

``` text
┌──────────────────────────────────────────────────────────────┐
│ Sidebar │ Top Header                                         │
│         ├─────────────────────────────────────────────────────┤
│         │ Page content                                       │
│         │                                                     │
│         │ Cards / tables / charts / activity                  │
│         │                                                     │
└─────────┴─────────────────────────────────────────────────────┘
```

Sidebar remains fixed on desktop.

Mobile: - Collapse sidebar into drawer. - Top header remains. - Tables
become horizontally scrollable or responsive cards. - Dashboard widgets
stack vertically. - Never simply shrink desktop UI until unreadable.

------------------------------------------------------------------------

# 4. Sidebar

The sidebar is dark navy.

Top: - IntelliCRM logo/wordmark - Optional organization selector

Navigation groups:

### Main

-   Dashboard
-   Leads
-   Customers
-   Projects
-   Tasks
-   Tickets
-   Messages

### Business

-   Invoices
-   Payments
-   Documents
-   Reports

### Intelligence

-   AI Insights
-   Ask IntelliCRM

### Administration

Visible only to permitted roles: - Team - Settings - Audit Logs

Bottom: - User avatar - User name - Role - Settings/logout menu

Active item: - Slightly lighter navy background - Small blue indicator
or subtle accent - White text

Do not use colorful icon backgrounds for every menu item.

------------------------------------------------------------------------

# 5. Global Top Header

Left: - Breadcrumb/page title where appropriate

Center: - Global search input - Placeholder:
`Search customers, leads, projects...` - Keyboard shortcut indicator if
implemented

Right: - Notification bell - Help icon - User avatar/profile menu

The header should remain clean and not compete with the page.

------------------------------------------------------------------------

# 6. Owner Dashboard --- Reference Screen

This is the primary screen that must visually match the approved image.

Page heading: `Dashboard`

Small supporting text:
`Overview of your business performance and customer health`

Top KPI row:

1.  Total Customers
2.  New Leads
3.  Active Projects
4.  At Risk Customers
5.  Revenue

Each KPI card: - White background - Small label - Large number - Small
trend indicator - Optional icon - Compact height - No gradient

Example:

``` text
TOTAL CUSTOMERS
1,284
↑ 8.4% this month
```

------------------------------------------------------------------------

## 6.1 Revenue & Pipeline

Large chart card.

Header: `Revenue & Pipeline`

Controls: - 7D - 30D - 90D - 12M

Use: - Revenue line/area chart - Pipeline amount - Tooltip on hover -
Legend

Do not use excessive chart decoration.

------------------------------------------------------------------------

## 6.2 Lead Conversion Funnel

Card beside/below revenue chart depending on viewport.

Stages: - New - Contacted - Qualified - Proposal - Won

Show: - count - conversion percentage

Use restrained colors.

------------------------------------------------------------------------

## 6.3 Attention Required

A priority business panel.

Rows may include: - Customer at high churn risk - Project predicted to
be delayed - Critical support ticket - Overdue payment

Each row: - Severity - Title - Entity - Reason - Action button

Example:

``` text
HIGH RISK
Acme Industries
Churn probability 82%
No interaction for 41 days
[Review]
```

This is one of the most important AI surfaces.

------------------------------------------------------------------------

## 6.4 Team Workload

Show employees with: - Active tasks - Overdue tasks - Capacity
percentage - Current status

Use compact progress bars.

Example:

``` text
Ananya     14 tasks     78% capacity
Karthik     9 tasks     52% capacity
Meera      18 tasks     94% capacity  ⚠
```

------------------------------------------------------------------------

## 6.5 Project Status

Show project counts: - On Track - At Risk - Delayed - Completed

Use compact chart or segmented visualization.

------------------------------------------------------------------------

## 6.6 Recent Activity

Timeline/list: - Lead created - Customer contacted - Ticket opened -
Payment received - Task completed - Project milestone updated

Each item: - actor - action - entity - relative time

------------------------------------------------------------------------

## 6.7 IntelliCRM Insights Strip

At the bottom of the dashboard:

``` text
Insights from IntelliCRM

3 customers need attention
2 projects may miss their deadlines
1 team member is overloaded

[Ask IntelliCRM]
```

This should look like a premium business insight component, not a
chatbot advertisement.

------------------------------------------------------------------------

# 7. Leads Page

Header: `Leads`

Actions: - Add Lead - Import - Export

Filters: - Search - Status - Source - Owner - Score - Date range

Table:

  -----------------------------------------------------------------------------
  Lead     Company   Source   Owner          Score Status   Last      Actions
                                                            Contact   
  -------- --------- -------- -------- ----------- -------- --------- ---------

  -----------------------------------------------------------------------------

Lead score: - 80--100: high - 50--79: medium - below 50: low

Clicking a lead opens Lead 360.

------------------------------------------------------------------------

# 8. Lead 360 Page

Sections: - Lead profile - Company information - Lead score - Score
explanation - Interaction timeline - Emails/messages - Notes - Tasks -
Recommended next action - Conversion controls

AI explanation:

``` text
Lead Score: 86 / 100

Why?
+ Frequent recent interactions
+ Pricing page visits
+ Requested proposal
+ High engagement
```

Never display a score without an explanation.

------------------------------------------------------------------------

# 9. Customers Page

Main table: - Customer - Company - Health - Projects - Open Tickets -
Last Interaction - Revenue - Owner

Health states: - Healthy - Watch - At Risk - Critical

Filters: - Health - Owner - Industry - Revenue - Last interaction

------------------------------------------------------------------------

# 10. Customer 360 Page

Header: - Company/customer name - Health score - Account owner - Contact
actions

Tabs:

### Overview

-   Customer health
-   Revenue
-   Active projects
-   Tickets
-   Recent activity

### Projects

-   Project list

### Tickets

-   Support history

### Communication

-   Internal/client communication

### Documents

-   Files

### Billing

-   Invoices and payments

### Activity

-   Complete audit/activity timeline

### AI Insights

-   Churn probability
-   Sentiment trend
-   Risk reasons
-   Recommended actions

------------------------------------------------------------------------

# 11. Projects Page

Table: - Project - Customer - Manager - Progress - Status - Due date -
Risk - Budget

Statuses: - Planning - Active - At Risk - Delayed - Completed - Archived

------------------------------------------------------------------------

# 12. Project Detail

Header: - Project name - Customer - Project status - Progress -
Deadline - Owner

Tabs: - Overview - Tasks - Milestones - Team - Files - Communication -
Activity - AI Risk

AI Risk panel:

``` text
Delay Risk: 74% — HIGH

Main factors:
- 4 overdue tasks
- Milestone 2 is behind schedule
- Team capacity at 91%
- Dependency waiting for client approval

Recommended:
1. Follow up with client
2. Reassign Task #184
3. Move milestone review to today
```

------------------------------------------------------------------------

# 13. Tasks Page

Views: - List - Kanban - My Tasks

Task fields: - Title - Project - Assignee - Priority - Status - Due
date - Estimated hours - Actual hours

AI-assisted prioritization: - Business impact - Deadline - Customer
risk - Dependency - Severity

Do not automatically change assignments without permission.

------------------------------------------------------------------------

# 14. Tickets Page

Ticket list: - Ticket ID - Customer - Subject - Category - Priority -
Sentiment - Assignee - SLA - Status

AI-generated fields: - predicted priority - sentiment - suggested
category - suggested response

Human staff must be able to override AI decisions.

------------------------------------------------------------------------

# 15. Ticket Detail

Layout: - Ticket information - Conversation - Customer context - AI
summary - Suggested response - Related project/customer - Internal
notes - Activity

AI panel:

``` text
Predicted Priority: HIGH
Confidence: 91%

Sentiment: Negative
Confidence: 88%

Reason:
Customer mentioned repeated service failures and missed deadline.
```

Buttons: - Accept - Edit - Reject

Never send an AI response automatically without the configured approval
policy.

------------------------------------------------------------------------

# 16. Messages

Provide: - Client conversations - Internal team conversations - Search -
Attachments - Read status - Typing indicator if real-time - Context link
to customer/project/ticket

Message composer: - Text - Attachment - Mention - Optional AI rewrite -
Optional AI summary

------------------------------------------------------------------------

# 17. Invoices & Payments

Invoices table: - Invoice number - Customer - Amount - Issue date - Due
date - Status

Statuses: - Draft - Sent - Partially Paid - Paid - Overdue - Cancelled

Dashboard cards: - Outstanding - Overdue - Paid this month - Revenue

------------------------------------------------------------------------

# 18. Team Page

Owner/manager only.

Show: - Employees - Roles - Workload - Active tasks - Performance
metrics - Availability

Employee detail: - Tasks - Projects - workload - activity - performance
indicators

Do not create invasive employee surveillance features.

------------------------------------------------------------------------

# 19. Reports

Report categories: - Sales - Customers - Projects - Support - Revenue -
Team workload - AI prediction accuracy

Provide: - Date range - Filters - Charts - Export CSV/PDF where
implemented

------------------------------------------------------------------------

# 20. AI Insights Page

This is a business intelligence page, not a chatbot.

Sections: - Customer risks - Lead opportunities - Project delays -
Ticket risks - Revenue anomalies - Team workload warnings

Every AI insight must contain: 1. Prediction 2. Confidence/probability
where appropriate 3. Main factors 4. Recommended action 5.
Timestamp/model version

------------------------------------------------------------------------

# 21. Ask IntelliCRM

Use a right-side drawer or modal.

Do not permanently occupy 30--40% of the dashboard.

Example:

``` text
Ask IntelliCRM

What customers need attention today?

──────────────────────────────

3 customers need immediate attention.

1. Acme Industries
   Churn risk: 82%
   Last interaction: 41 days ago

2. Beta Systems
   Payment overdue: 19 days

3. Gamma Labs
   Negative support sentiment

[View details]
```

The assistant must obey RBAC.

------------------------------------------------------------------------

# 22. Client Portal

The client should NOT see internal CRM terminology.

Client navigation: - Home - My Projects - Requests - Messages -
Documents - Invoices - Profile

Home: - project progress - upcoming milestones - open requests -
invoices - recent communication

No internal employee workload, internal notes, lead scores, or private
AI predictions.

------------------------------------------------------------------------

# 23. Notifications

Types: - Task assigned - Task overdue - Ticket assigned - Ticket
escalation - Payment received - Invoice overdue - Project risk -
Customer risk - Mention - Message

Use a notification center.

Do not create excessive popups.

------------------------------------------------------------------------

# 24. Forms and Modals

Forms should be: - compact - clearly labelled - keyboard accessible -
validated inline

Required fields should be visibly marked.

Buttons: - Primary: blue - Secondary: neutral - Destructive: red

Always confirm destructive actions.

------------------------------------------------------------------------

# 25. Loading, Empty and Error States

Every page must have: - skeleton loading - empty state - error state -
retry action

Example empty state:

``` text
No customers found

Try changing your filters or add your first customer.

[Add Customer]
```

Avoid cartoon illustrations.

------------------------------------------------------------------------

# 26. Responsive Rules

Breakpoints: - mobile: \<640px - tablet: 640--1024px - desktop: \>1024px

Desktop: - sidebar visible

Tablet: - collapsible sidebar

Mobile: - drawer navigation - one-column dashboard - bottom/action
controls where appropriate

------------------------------------------------------------------------

# 27. Accessibility

Minimum: - semantic HTML - keyboard navigation - visible focus -
sufficient contrast - labels for inputs - ARIA where required - no
information conveyed only by color

------------------------------------------------------------------------

# 28. Component Architecture

Recommended:

``` text
src/
  components/
    layout/
    navigation/
    dashboard/
    charts/
    tables/
    forms/
    customers/
    leads/
    projects/
    tasks/
    tickets/
    messages/
    billing/
    ai/
    notifications/
    common/
```

Use reusable components instead of duplicating page-specific UI.
