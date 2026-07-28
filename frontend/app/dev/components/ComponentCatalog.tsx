"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button/Button";
import { IconButton } from "@/components/ui/IconButton/IconButton";
import { Chip } from "@/components/ui/Chip/Chip";
import { Badge } from "@/components/ui/Badge/Badge";
import { Switch } from "@/components/ui/Switch/Switch";
import { SegmentedControl } from "@/components/ui/SegmentedControl/SegmentedControl";
import { TopHeader } from "@/components/ui/TopHeader/TopHeader";
import { AvatarInitial } from "@/components/ui/AvatarInitial/AvatarInitial";
import { Banner } from "@/components/ui/Banner/Banner";
import { BottomSheet } from "@/components/ui/BottomSheet/BottomSheet";
import { Input } from "@/components/ui/Input/Input";
import { Textarea } from "@/components/ui/Textarea/Textarea";
import { Select } from "@/components/ui/Select/Select";
import { DatePicker } from "@/components/ui/DatePicker/DatePicker";
import { TagInput } from "@/components/ui/TagInput/TagInput";
import Loading from "@/app/loading";
import styles from "./page.module.css";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={styles.section}>
      <h2 className={`textSectionTitle ${styles.sectionTitle}`}>{title}</h2>
      {children}
    </div>
  );
}

function StateRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <span className={`textCaption ${styles.stateLabel}`}>{label}</span>
      <div className={styles.row}>{children}</div>
    </div>
  );
}

function CatalogColumn() {
  const [switchOn, setSwitchOn] = useState(true);
  const [segment, setSegment] = useState("all");
  const [sheetState, setSheetState] = useState<"closed" | "normal" | "loading" | "error" | "empty">(
    "closed",
  );
  const [tags, setTags] = useState<string[]>(["Acme"]);
  const [text, setText] = useState("");
  const [date, setDate] = useState("1990-01-01");

  return (
    <>
      <Section title="Boot/splash (app/loading.tsx)">
        <Loading />
      </Section>

      <Section title="Button">
        <StateRow label="primary / secondary / outline (default)">
          <Button variant="primary" width="intrinsic">
            Primary
          </Button>
          <Button variant="secondary" width="intrinsic">
            Secondary
          </Button>
          <Button variant="outline" width="intrinsic">
            Outline
          </Button>
        </StateRow>
        <StateRow label="disabled / loading / error">
          <Button width="intrinsic" disabled>
            Disabled
          </Button>
          <Button width="intrinsic" state="loading">
            Loading
          </Button>
          <Button width="intrinsic" state="error">
            Try again
          </Button>
        </StateRow>
      </Section>

      <Section title="IconButton">
        <StateRow label="default / disabled / heart / heartFilled">
          <IconButton icon="settings" />
          <IconButton icon="close" disabled />
          <IconButton icon="heart" />
          <IconButton icon="heartFilled" />
        </StateRow>
      </Section>

      <Section title="Chip">
        <StateRow label="inactive / active / disabled">
          <Chip>Tops</Chip>
          <Chip active>Tops</Chip>
          <Chip disabled>Tops</Chip>
        </StateRow>
      </Section>

      <Section title="Badge">
        <StateRow label="citation / status / muted / count">
          <Badge tone="citation">1</Badge>
          <Badge tone="status">Connected</Badge>
          <Badge tone="muted">Coming soon</Badge>
          <Badge tone="count">3</Badge>
        </StateRow>
      </Section>

      <Section title="Switch">
        <StateRow label="on / off / disabled">
          <Switch checked={switchOn} onChange={setSwitchOn} aria-label="Push notifications" />
          <Switch checked={false} onChange={() => {}} aria-label="Off example" />
          <Switch checked={false} onChange={() => {}} disabled aria-label="Disabled example" />
        </StateRow>
      </Section>

      <Section title="SegmentedControl">
        <StateRow label="default / disabled">
          <SegmentedControl
            options={[
              { value: "all", label: "All" },
              { value: "favorited", label: "Favorited" },
            ]}
            value={segment}
            onChange={setSegment}
          />
          <SegmentedControl
            options={[
              { value: "all", label: "All" },
              { value: "favorited", label: "Favorited" },
            ]}
            value="all"
            onChange={() => {}}
            disabled
          />
        </StateRow>
      </Section>

      <Section title="TopHeader">
        <TopHeader title="Closet" subtitle="12 items" onBack={() => {}} rightSlot={{ kind: "none" }} />
      </Section>

      <Section title="AvatarInitial">
        <StateRow label="sizes 32 / 48 / 64">
          <AvatarInitial initial="A" size={32} />
          <AvatarInitial initial="A" size={48} />
          <AvatarInitial initial="A" size={64} />
        </StateRow>
      </Section>

      <Section title="Banner">
        <StateRow label="offline / error / info">
          <Banner variant="offline">You&apos;re offline. Some actions are unavailable.</Banner>
        </StateRow>
        <StateRow label="">
          <Banner variant="error" action={{ label: "Retry", onClick: () => {} }}>
            That didn&apos;t save.
          </Banner>
        </StateRow>
        <StateRow label="">
          <Banner variant="info">I&apos;m working with a small closet.</Banner>
        </StateRow>
      </Section>

      <Section title="BottomSheet">
        <StateRow label="normal / loading / error / empty">
          <Button width="intrinsic" onClick={() => setSheetState("normal")}>
            Open (normal)
          </Button>
          <Button width="intrinsic" onClick={() => setSheetState("loading")}>
            Open (loading)
          </Button>
          <Button width="intrinsic" onClick={() => setSheetState("error")}>
            Open (error)
          </Button>
          <Button width="intrinsic" onClick={() => setSheetState("empty")}>
            Open (empty)
          </Button>
        </StateRow>
        <BottomSheet
          open={sheetState !== "closed"}
          onClose={() => setSheetState("closed")}
          title="Item options"
          state={sheetState === "closed" ? "normal" : sheetState}
          errorAction={{ label: "Try again", onClick: () => setSheetState("normal") }}
          rows={[
            { label: "Edit", onSelect: () => {} },
            { label: "Log as worn today", onSelect: () => {} },
            { label: "Delete", tone: "danger", onSelect: () => {} },
          ]}
        />
      </Section>

      <Section title="Input">
        <StateRow label="default / error / disabled / password">
          <Input label="Email" type="email" value={text} onChange={setText} placeholder="you@example.com" />
          <Input label="Email" value="bad" onChange={() => {}} error="Enter a valid email address." />
          <Input label="Email" value="" onChange={() => {}} disabled />
          <Input label="Password" type="password" value="secret" onChange={() => {}} />
        </StateRow>
      </Section>

      <Section title="Textarea">
        <StateRow label="default / error">
          <Textarea label="Notes" value="" onChange={() => {}} />
          <Textarea label="Notes" value="" onChange={() => {}} error="This field is required." />
        </StateRow>
      </Section>

      <Section title="Select">
        <StateRow label="default / error">
          <Select
            label="Top size"
            value="s"
            onChange={() => {}}
            options={[
              { value: "xs", label: "XS" },
              { value: "s", label: "S" },
            ]}
          />
          <Select
            label="Top size"
            value="s"
            onChange={() => {}}
            error="This field is required."
            options={[
              { value: "xs", label: "XS" },
              { value: "s", label: "S" },
            ]}
          />
        </StateRow>
      </Section>

      <Section title="DatePicker">
        <StateRow label="default">
          <DatePicker label="Birth date" value={date} onChange={setDate} />
        </StateRow>
      </Section>

      <Section title="TagInput">
        <StateRow label="default">
          <TagInput label="Brands to avoid" values={tags} onChange={setTags} placeholder="Type and press Enter" />
        </StateRow>
      </Section>
    </>
  );
}

/**
 * Dev-only component catalog — spec.md FR-005a. Renders every documented
 * state of all sixteen shared components in both themes side by side, so
 * the state-matrix definition-of-done item is mechanically checkable.
 */
export function ComponentCatalog() {
  return (
    <div className={styles.page}>
      <div className={styles.themeColumn} data-theme="light">
        <h2 className="textSectionTitle">Light theme</h2>
        <CatalogColumn />
      </div>
      <div className={styles.themeColumn} data-theme="dark">
        <h2 className="textSectionTitle">Dark theme</h2>
        <CatalogColumn />
      </div>
    </div>
  );
}
